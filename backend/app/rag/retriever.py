
from sqlalchemy import select, cast, String, func

from app.database.connection import SessionLocal
from app.database.models import Document, DocumentChunk
from app.rag.embeddings import create_embedding


def retrieve_relevant_chunks(
    question: str,
    user_id: int,
    limit: int = 12,
    max_distance: float = 0.65,
    document_id: int | None = None,
):
    question_embedding = create_embedding(question)

    db = SessionLocal()

    try:
        distance = DocumentChunk.embedding.cosine_distance(
            question_embedding
        )

        ranked_chunks = (
            select(
                DocumentChunk.id.label("chunk_id"),
                distance.label("distance"),
                func.row_number()
                .over(
                    partition_by=(
                        DocumentChunk.document_id,
                        DocumentChunk.chunk_text,
                    ),
                    order_by=(distance, DocumentChunk.id),
                )
                .label("duplicate_rank"),
            )
            .join(
                Document,
                cast(Document.id, String) == DocumentChunk.document_id
            )
            .where(
                Document.user_id == user_id,
                *(
                    [Document.id == document_id]
                    if document_id is not None
                    else []
                ),
            )
            .subquery()
        )

        statement = (
            select(DocumentChunk, ranked_chunks.c.distance)
            .join(
                ranked_chunks,
                DocumentChunk.id == ranked_chunks.c.chunk_id,
            )
            .where(
                ranked_chunks.c.duplicate_rank == 1,
                ranked_chunks.c.distance <= max_distance,
            )
            .order_by(ranked_chunks.c.distance, DocumentChunk.id)
            .limit(limit)
        )

        results = db.execute(statement).all()

        return [chunk for chunk, _ in results]

    finally:
        db.close()

