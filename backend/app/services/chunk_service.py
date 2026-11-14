from app.database.connection import SessionLocal
from app.database.models import DocumentChunk

from app.rag.embeddings import create_embedding
from app.rag.loader import ExtractedPage
from app.rag.structure import structure_document_pages


def process_document(document_id: int, text: str | list[ExtractedPage]):
    pages = (
        text
        if isinstance(text, list)
        else [ExtractedPage(page_number=None, text=text)]
    )
    chunks = structure_document_pages(pages)
    db = SessionLocal()

    try:
        for chunk in chunks:
            embedding_text = (
                f"{chunk.section_heading}\n{chunk.text}"
                if chunk.section_heading
                else chunk.text
            )
            embedding = create_embedding(embedding_text)

            document_chunk = DocumentChunk(
                document_id=document_id,
                chunk_text=chunk.text,
                embedding=embedding,
                page_number=chunk.page_number,
                section_heading=chunk.section_heading,
            )
            db.add(document_chunk)

        db.commit()
        return len(chunks)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
