from app.database.connection import SessionLocal
from app.database.models import DocumentChunk

from app.rag.chunker import chunk_text
from app.rag.embeddings import create_embedding



def process_document(document_id: int, text: str):
    chunks = chunk_text(text)
    db = SessionLocal()

    try:
        for chunk in chunks:
            embedding = create_embedding(chunk)

            document_chunk = DocumentChunk(
                document_id=document_id,
                chunk_text=chunk,
                embedding=embedding
            )
            db.add(document_chunk)

        db.commit()
        return len(chunks)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
