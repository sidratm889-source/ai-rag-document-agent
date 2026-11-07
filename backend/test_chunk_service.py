from app.services.chunk_service import process_document

text = """
Our restaurant opens at 10 AM every day.

Breakfast is served from 10 AM to 12 PM.

Lunch is served from 1 PM to 4 PM.

Dinner is served from 6 PM to 10 PM.

We offer pizza, burgers, pasta and salads.
"""

document_id = 1

if __name__ == "__main__":
    count = process_document(document_id, text)
    print("Chunks saved:", count)
from unittest.mock import MagicMock
import pytest

from app.services import chunk_service


def test_process_document_success(monkeypatch):
    mock_db = MagicMock()

    monkeypatch.setattr(chunk_service, "SessionLocal", lambda: mock_db)
    monkeypatch.setattr(
        chunk_service, "chunk_text",
        lambda text: ["chunk one", "chunk two"]
    )
    monkeypatch.setattr(
        chunk_service, "create_embedding",
        lambda chunk: [0.1, 0.2, 0.3]
    )

    result = chunk_service.process_document(1, "sample text")

    assert result == 2
    assert mock_db.add.call_count == 2
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()


def test_process_document_rolls_back_when_embedding_fails(monkeypatch):
    mock_db = MagicMock()

    monkeypatch.setattr(chunk_service, "SessionLocal", lambda: mock_db)
    monkeypatch.setattr(
        chunk_service, "chunk_text",
        lambda text: ["chunk one"]
    )

    def fail_embedding(chunk):
        raise ValueError("Embedding failed")

    monkeypatch.setattr(chunk_service, "create_embedding", fail_embedding)

    with pytest.raises(ValueError, match="Embedding failed"):
        chunk_service.process_document(1, "sample text")

    mock_db.rollback.assert_called_once()
    mock_db.close.assert_called_once()


def test_process_document_rolls_back_when_commit_fails(monkeypatch):
    mock_db = MagicMock()
    mock_db.commit.side_effect = RuntimeError("Commit failed")

    monkeypatch.setattr(chunk_service, "SessionLocal", lambda: mock_db)
    monkeypatch.setattr(
        chunk_service, "chunk_text",
        lambda text: ["chunk one"]
    )
    monkeypatch.setattr(
        chunk_service, "create_embedding",
        lambda chunk: [0.1, 0.2, 0.3]
    )

    with pytest.raises(RuntimeError, match="Commit failed"):
        chunk_service.process_document(1, "sample text")

    mock_db.rollback.assert_called_once()
    mock_db.close.assert_called_once()