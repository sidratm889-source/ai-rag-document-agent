import pytest
from types import SimpleNamespace

from app.services import llm


def test_generate_answer_success(monkeypatch):
    def fake_chat(**kwargs):
        assert kwargs["model"] == "llama3.2:1b"
        assert kwargs["options"] == {
            "temperature": 0,
            "num_predict": 512,
        }
        return SimpleNamespace(
            message=SimpleNamespace(content="Answer from document")
        )

    monkeypatch.setattr(llm, "get_client", lambda: SimpleNamespace(chat=fake_chat))
    monkeypatch.setattr(llm.os, "getenv", lambda key, default=None: default)

    result = llm.generate_answer("What is this document about?", "Sample context")

    assert result == "Answer from document"


def test_generate_answer_returns_empty_string(monkeypatch):
    monkeypatch.setattr(
        llm,
        "get_client",
        lambda: SimpleNamespace(
            chat=lambda **kwargs: SimpleNamespace(
                message=SimpleNamespace(content=None)
            )
        ),
    )

    result = llm.generate_answer("Question", "Context")

    assert result == ""


def test_generate_answer_logs_and_reraises_exception(monkeypatch):
    def failing_chat(**kwargs):
        raise RuntimeError("Ollama unavailable")

    monkeypatch.setattr(
        llm,
        "get_client",
        lambda: SimpleNamespace(chat=failing_chat),
    )

    with pytest.raises(RuntimeError, match="Ollama unavailable"):
        llm.generate_answer("Question", "Context")