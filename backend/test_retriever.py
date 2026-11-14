
from unittest.mock import patch, MagicMock

from sqlalchemy.dialects import postgresql

from app.rag.retriever import retrieve_relevant_chunks



def test_retriever_returns_relevant_chunks():
    fake_chunk = MagicMock()
    fake_chunk.document_id = 1
    fake_chunk.chunk_text = "The restaurant opens at 10 AM."

    with patch("app.rag.retriever.create_embedding", return_value=[0.1] * 384), \
         patch("app.rag.retriever.SessionLocal") as mock_session:

        db = mock_session.return_value
        db.execute.return_value.all.return_value = [(fake_chunk, 0.20)]

        results = retrieve_relevant_chunks(
            "When does the restaurant open?",
             user_id=1,
            limit=3,
            max_distance=0.65
        )

    assert len(results) == 1
    assert results[0].chunk_text == "The restaurant opens at 10 AM."



def test_retriever_deduplicates_before_limit_and_applies_distance_filter():
    close_chunk = MagicMock()

    db = MagicMock()
    db.execute.return_value.all.return_value = [
        (close_chunk, 0.40),
    ]

    with patch("app.rag.retriever.SessionLocal", return_value=db), \
         patch("app.rag.retriever.create_embedding", return_value=[0.1, 0.2]):

        result = retrieve_relevant_chunks(
            question="What is AI?",
            user_id=1,
            max_distance=0.65
        )

    assert result == [close_chunk]
    sql = str(
        db.execute.call_args.args[0].compile(
            dialect=postgresql.dialect()
        )
    ).casefold()
    assert (
        "row_number() over (partition by document_chunks.document_id, "
        "document_chunks.chunk_text"
    ) in sql
    assert "document.user_id =" in sql
    assert ".distance <=" in sql
    assert "limit" in sql
    db.close.assert_called_once()


def test_retriever_can_scope_to_one_owned_document():
    db = MagicMock()
    db.execute.return_value.all.return_value = []

    with patch(
        "app.rag.retriever.SessionLocal",
        return_value=db,
    ), patch(
        "app.rag.retriever.create_embedding",
        return_value=[0.1, 0.2],
    ):
        retrieve_relevant_chunks(
            question="What is the total?",
            user_id=4,
            document_id=28,
        )

    sql = str(
        db.execute.call_args.args[0].compile(
            dialect=postgresql.dialect()
        )
    )
    assert "document.user_id =" in sql
    assert "document.id =" in sql


def test_retrieve_relevant_chunks_returns_empty_list():
    db = MagicMock()
    db.execute.return_value.all.return_value = []

    with patch(
        "app.rag.retriever.SessionLocal",
        return_value=db
    ), patch(
        "app.rag.retriever.create_embedding",
        return_value=[0.1, 0.2]
    ):
        result = retrieve_relevant_chunks(
            question="What is AI?",
            user_id=1
        )

    assert result == []
    db.close.assert_called_once()