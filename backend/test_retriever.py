
from unittest.mock import patch, MagicMock

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



def test_retrieve_relevant_chunks_excludes_distant_chunks():
    close_chunk = MagicMock()
    distant_chunk = MagicMock()

    db = MagicMock()
    db.execute.return_value.all.return_value = [
        (close_chunk, 0.40),
        (distant_chunk, 0.80),
    ]

    with patch("app.rag.retriever.SessionLocal", return_value=db), \
         patch("app.rag.retriever.create_embedding", return_value=[0.1, 0.2]):

        result = retrieve_relevant_chunks(
            question="What is AI?",
            user_id=1,
            max_distance=0.65
        )

    assert result == [close_chunk]
    assert distant_chunk not in result
    db.close.assert_called_once()


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