import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pathlib import Path
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import Document, DocumentChunk
from app.rag.loader import extract_text_from_pdf, validate_extracted_text
from app.services.chunk_service import process_document
from app.api.dependencies import get_current_user, get_db
from app.database.models import User


router = APIRouter(prefix="/documents", tags=["documents"])
upload_dir = Path("uploads")
upload_dir.mkdir(exist_ok=True)





MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.get("")
def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
    sort: Literal["uploaded_at"] = Query(default="uploaded_at"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Document).filter(Document.user_id == current_user.id)

    search_term = search.strip() if search else ""
    if search_term:
        query = query.filter(Document.filename.ilike(f"%{search_term}%"))

    total = query.count()
    date_order = (
        Document.uploaded_at.desc().nullslast()
        if order == "desc"
        else Document.uploaded_at.asc().nullslast()
    )
    id_order = Document.id.desc() if order == "desc" else Document.id.asc()
    documents = (
        query.order_by(date_order, id_order)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": [
            {
                "id": document.id,
                "filename": document.filename,
                "uploaded_at": document.uploaded_at,
            }
            for document in documents
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.post("/upload")
def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    original_filename = (
        (file.filename or "").replace("\\", "/").split("/")[-1]
    )

    if not original_filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="The filename must end with .pdf."
        )

    content = file.file.read(MAX_FILE_SIZE + 1)

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File size must not exceed 10 MB."
        )

    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid PDF file."
        )

    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{uuid.uuid4().hex}.pdf"

    db = SessionLocal()
    document = None

    try:
        # Save the file temporarily
        file_path.write_bytes(content)

        # Extract and validate text before creating a DB record
        try:
            text = extract_text_from_pdf(str(file_path))
            text = validate_extracted_text(text)
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error)
            ) from error

        # Create the document record
        document = Document(
    filename=original_filename,
    file_path=str(file_path),
    user_id=current_user.id,
)
        db.add(document)
        db.commit()
        db.refresh(document)

        # Create chunks and embeddings
        process_document(document.id, text)

        return {
            "message": "Document uploaded and processed successfully",
            "document_id": document.id,
            "filename": document.filename,
        }

    except HTTPException:
        db.rollback()

        if document is not None and document.id is not None:
            db.delete(document)
            db.commit()

        if file_path.exists():
            file_path.unlink()

        raise

    except Exception as error:
        db.rollback()

        if document is not None and document.id is not None:
            try:
                # Remove chunks if processing created any
                db.query(DocumentChunk).filter(
                    DocumentChunk.document_id == document.id
                ).delete(synchronize_session=False)

                db.delete(document)
                db.commit()
            except Exception:
                db.rollback()

        if file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=500,
            detail="Could not upload and process the document."
        ) from error

    finally:
        db.close()
        file.file.close()
