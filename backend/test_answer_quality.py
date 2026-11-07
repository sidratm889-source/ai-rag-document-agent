
from unittest.mock import patch

from app.services.llm import generate_answer


def test_answer_uses_document_context():
    with patch("app.services.llm.get_client") as mock_get_client:
        mock_get_client.return_value.chat.return_value.message.content = (
            "The restaurant opens at 10 AM."
        )

        answer = generate_answer(
            question="When does the restaurant open?",
            context="The restaurant opens at 10 AM."
        )

    messages = mock_get_client.return_value.chat.call_args.kwargs["messages"]
    assert "The restaurant opens at 10 AM." in messages[1]["content"]
    assert "10 AM" in answer


def test_missing_information_is_not_invented():
    with patch("app.services.llm.get_client") as mock_get_client:
        mock_get_client.return_value.chat.return_value.message.content = (
            "The document does not provide this information."
        )

        answer = generate_answer(
            question="Who owns the restaurant?",
            context="The restaurant opens at 10 AM."
        )

    assert "does not provide" in answer.lower()
