
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.agent.tools import search_document_content
from unittest.mock import MagicMock, patch

from app.agent.tools import (
    search_document_content,
    query_business_data,
)
from app.database.models import (
    Document,
    Conversation,
    ConversationMessage,
)


def assert_sqlalchemy_expression(mock_call, expected_expression):
    mock_call.assert_called_once()
    assert mock_call.call_args.args[-1].compare(expected_expression)


def assert_user_filter(mock_db, expected_filter):
    filter_mock = mock_db.query.return_value.filter
    assert_sqlalchemy_expression(filter_mock, expected_filter)


def test_empty_question_is_rejected():
    with pytest.raises(ValueError):
        search_document_content("", user_id=1)


def test_question_too_long_is_rejected():
    with pytest.raises(ValueError):
        search_document_content("a" * 1001, user_id=1)


def test_valid_question_returns_results():
    chunk = SimpleNamespace(
        document_id=7,
        chunk_text="The restaurant opens at 10 AM.",
    )

    with patch(
        "app.agent.tools.retrieve_relevant_chunks",
        return_value=[chunk],
    ) as retrieve:
        results = search_document_content(
            "When does the restaurant open?",
            user_id=1,
        )

    retrieve.assert_called_once_with(
        "When does the restaurant open?",
        user_id=1,
        limit=3,
    )
    assert results == [
        {
            "document_id": 7,
            "chunk": "The restaurant opens at 10 AM.",
        }
    ]
def test_business_tool_rejects_invalid_action():
    with pytest.raises(ValueError):
        query_business_data("delete_all_data", user_id=1)


def test_business_tool_rejects_invalid_user_id():
    with pytest.raises(ValueError):
        query_business_data("document_count", user_id=0)


def test_document_count_returns_user_count():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.scalar.return_value = 5

    with patch("app.agent.tools.SessionLocal", return_value=mock_db):
        result = query_business_data("document_count", user_id=10)

    assert result == {"document_count": 5}
    assert_user_filter(mock_db, Document.user_id == 10)
    mock_db.close.assert_called_once()


def test_document_list_returns_documents():
    mock_db = MagicMock()

    document = SimpleNamespace(
        id=1,
        filename="report.pdf",
        uploaded_at=None,
    )

    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        document
    ]

    with patch("app.agent.tools.SessionLocal", return_value=mock_db):
        result = query_business_data("document_list", user_id=10)

    assert result == {
        "documents": [
            {
                "id": 1,
                "filename": "report.pdf",
                "uploaded_at": None,
            }
        ]
    }

    assert_user_filter(mock_db, Document.user_id == 10)
    mock_db.close.assert_called_once()


def test_conversation_count_returns_user_count():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.scalar.return_value = 3

    with patch("app.agent.tools.SessionLocal", return_value=mock_db):
        result = query_business_data("conversation_count", user_id=10)

    assert result == {"conversation_count": 3}
    assert_user_filter(mock_db, Conversation.user_id == 10)
    mock_db.close.assert_called_once()
def test_recent_conversations_returns_user_conversations():
    mock_db = MagicMock()

    conversation = SimpleNamespace(
        conversation_id="conv-123",
        created_at=None,
    )

    (
        mock_db.query.return_value
        .filter.return_value
        .order_by.return_value
        .limit.return_value
        .all.return_value
    ) = [conversation]

    with patch("app.agent.tools.SessionLocal", return_value=mock_db):
        result = query_business_data(
            "recent_conversations",
            user_id=10,
        )

    assert result == {
        "conversations": [
            {
                "conversation_id": "conv-123",
                "created_at": None,
            }
        ]
    }

    assert_user_filter(mock_db, Conversation.user_id == 10)
    mock_db.close.assert_called_once()


def test_message_count_returns_user_message_count():
    mock_db = MagicMock()

    (
        mock_db.query.return_value
        .join.return_value
        .filter.return_value
        .scalar.return_value
    ) = 12

    with patch("app.agent.tools.SessionLocal", return_value=mock_db):
        result = query_business_data("message_count", user_id=10)

    assert result == {"message_count": 12}

    join_mock = mock_db.query.return_value.join
    join_mock.assert_called_once()
    assert join_mock.call_args.args[0] is Conversation
    assert join_mock.call_args.args[1].compare(
        Conversation.conversation_id == ConversationMessage.conversation_id
    )

    assert_sqlalchemy_expression(
        mock_db.query.return_value.join.return_value.filter,
        Conversation.user_id == 10,
    )

    mock_db.close.assert_called_once()
def test_query_business_data_rejects_non_string_action():
    with pytest.raises(ValueError, match="Action must be a string"):
        query_business_data(action=123, user_id=1)
def test_search_document_content_rejects_non_string_question():
    with pytest.raises(ValueError, match="Question must be a string"):
        search_document_content(123, user_id=1)


def test_search_document_content_rejects_non_integer_user_id():
    with pytest.raises(ValueError, match="Invalid user ID"):
        search_document_content("Hello", user_id="1")
    