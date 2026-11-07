
from sqlalchemy import select, cast, String

from app.database.connection import SessionLocal
from app.database.models import Document, DocumentChunk
from app.rag.embeddings import create_embedding


def retrieve_relevant_chunks(
    question: str,
    user_id: int,
    limit: int = 3,
    max_distance: float = 0.65
):
    question_embedding = create_embedding(question)

    db = SessionLocal()

    try:
        distance = DocumentChunk.embedding.cosine_distance(
            question_embedding
        )

        statement = (
            select(DocumentChunk, distance.label("distance"))
            .join(
                Document,
                cast(Document.id, String) == DocumentChunk.document_id
            )
            .where(Document.user_id == user_id)
            .order_by(distance)
            .limit(limit)
        )

        results = db.execute(statement).all()

        relevant_chunks = []

        for chunk, distance_value in results:
            if distance_value <= max_distance:
                relevant_chunks.append(chunk)

        return relevant_chunks

    finally:
        db.close()

