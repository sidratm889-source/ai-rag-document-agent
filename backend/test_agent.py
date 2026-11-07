
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest


from types import SimpleNamespace
from app.rag.embeddings import create_embedding

from app.agent.tools import search_document_content
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.agent.agent import (
    _asks_about_previous_message,
    load_chat_history,
    run_agent,
    save_chat_message,
    save_audit_log,
    create_conversation,
    save_conversation,
)


from app.database.models import AuditLog, Conversation, ConversationMessage


def test_agent_returns_final_answer():
    fake_client = MagicMock()

    fake_client.chat.return_value = SimpleNamespace(
        message=SimpleNamespace(
            content="Hello! How can I help?",
            tool_calls=[]
        )
    )

    with patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ), patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch("app.agent.agent.save_chat_message"):
        answer = run_agent(
            question="Hello",
            conversation_id="test-direct-answer",
            user_id=1,
        )

    assert answer == "Hello! How can I help?"
    fake_client.chat.assert_called_once()
    
def test_agent_calls_search_tool_and_returns_answer():
    fake_client = MagicMock()

    tool_call = SimpleNamespace(
        id="call-123",
        function=SimpleNamespace(
            name="search_document_content",
            arguments={"question": "When does the restaurant open?"}
        )
    )

    tool_response = SimpleNamespace(
        message=SimpleNamespace(
            content=None,
            tool_calls=[tool_call]
        )
    )

    final_response = SimpleNamespace(
        message=SimpleNamespace(
            content="The restaurant opens at 10 AM.",
            tool_calls=[]
        )
    )

    fake_client.chat.side_effect = [
        tool_response,
        final_response
    ]

    with patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ), patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch(
        "app.agent.agent.save_chat_message",
    ), patch(
        "app.agent.agent.search_document_content",
        return_value=[
            {
                "document_id": 1,
                "chunk": "The restaurant opens at 10 AM."
            }
        ],
    ) as mock_search:

        answer = run_agent(
            question="When does the restaurant open?",
            conversation_id="test-tool-call",
            user_id=1,
        )

    assert answer == "The restaurant opens at 10 AM."
    mock_search.assert_called_once_with(
        "When does the restaurant open?",
        user_id=1,
    )
    assert fake_client.chat.call_count == 2


def test_agent_calls_business_data_tool_and_returns_answer():
    tool_call = SimpleNamespace(
        id="call-business-data",
        function=SimpleNamespace(
            name="query_business_data",
            arguments={"action": "document_count"},
        ),
    )
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        SimpleNamespace(
            message=SimpleNamespace(content=None, tool_calls=[tool_call])
        ),
        SimpleNamespace(
            message=SimpleNamespace(
                content="You have 3 documents.",
                tool_calls=[],
            )
        ),
    ]

    with patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ), patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch(
        "app.agent.agent.save_chat_message",
    ), patch(
        "app.agent.agent.save_audit_log",
    ), patch(
        "app.agent.agent.query_business_data",
        return_value={"document_count": 3},
    ) as mock_query:
        answer = run_agent(
            question="How many documents do I have?",
            conversation_id="test-business-data-tool-call",
            user_id=1,
        )

    assert answer == "You have 3 documents."
    mock_query.assert_called_once_with("document_count", user_id=1)
    assert fake_client.chat.call_count == 2


def test_agent_falls_back_to_user_question_when_tool_arguments_omit_question():
    tool_call = SimpleNamespace(
        id="call-missing-question",
        function=SimpleNamespace(
            name="search_document_content",
            arguments={"query": "unexpected argument name"},
        ),
    )
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        SimpleNamespace(
            message=SimpleNamespace(content=None, tool_calls=[tool_call])
        ),
        SimpleNamespace(
            message=SimpleNamespace(
                content="The sum of 2 and 3 is 5.",
                tool_calls=[],
            )
        ),
    ]

    with patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ), patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch(
        "app.agent.agent.save_chat_message",
    ), patch(
        "app.agent.agent.save_audit_log",
    ), patch(
        "app.agent.agent.search_document_content",
        return_value=[{"chunk": "2 + 3 = 5"}],
    ) as mock_search:
        answer = run_agent(
            question="what sum of 2 and 3 is?",
            conversation_id="test-missing-tool-question",
            user_id=1,
        )

    assert answer == "The sum of 2 and 3 is 5."
    mock_search.assert_called_once_with(
        "what sum of 2 and 3 is?",
        user_id=1,
    )


def test_agent_handles_search_tool_error():
    fake_client = MagicMock()

    tool_call = SimpleNamespace(
        id="call-error",
        function=SimpleNamespace(
            name="search_document_content",
            arguments={"question": "When does the restaurant open?"}
        )
    )

    tool_response = SimpleNamespace(
        message=SimpleNamespace(
            content=None,
            tool_calls=[tool_call]
        )
    )

    final_response = SimpleNamespace(
        message=SimpleNamespace(
            content="Sorry, I couldn't retrieve the document information.",
            tool_calls=[]
        )
    )

    fake_client.chat.side_effect = [
        tool_response,
        final_response
    ]

    with patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ), patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch(
        "app.agent.agent.save_chat_message",
    ), patch(
        "app.agent.agent.search_document_content",
        side_effect=RuntimeError("Database connection failed"),
    ):

        answer = run_agent(
            question="When does the restaurant open?",
            conversation_id="test-tool-error",
            user_id=1,
        )

    assert answer == (
        "Sorry, I couldn't retrieve the document information."
    )
    assert fake_client.chat.call_count == 2


def test_agent_answers_what_previous_message_was():
    previous_messages = [
        {"role": "user", "content": "First question"},
        {"role": "assistant", "content": "First answer"},
        {"role": "user", "content": "Most recent question"},
    ]

    with patch(
        "app.agent.agent.load_chat_history",
        return_value=previous_messages,
    ), patch("app.agent.agent.save_chat_message") as mock_save:
        answer = run_agent(
            question=" What did I ask before? ",
            conversation_id="test-previous-message",
            user_id=1,
        )

    assert answer == "Your previous message was: Most recent question"
    assert mock_save.call_count == 2
    assert mock_save.call_args_list[0].args == (
        "test-previous-message",
        "user",
        " What did I ask before? ",
    )
    assert mock_save.call_args_list[1].args == (
        "test-previous-message",
        "assistant",
        "Your previous message was: Most recent question",
    )


def test_detects_previous_message_question():
    assert _asks_about_previous_message(
        "What did I ask you in my previous message?"
    )


def test_detects_previous_question():
    assert _asks_about_previous_message(
        "What was my last question?"
    )


def test_rejects_normal_question():
    assert not _asks_about_previous_message("What is Python?")


def test_agent_answers_informal_previous_message_question():
    previous_messages = [
        {"role": "user", "content": "My earlier question"},
        {"role": "assistant", "content": "Earlier answer"},
    ]

    with patch(
        "app.agent.agent.load_chat_history",
        return_value=previous_messages,
    ), patch("app.agent.agent.save_chat_message"):
        answer = run_agent(
            question="what i ask from previous message",
            conversation_id="test-informal-previous-message",
            user_id=1,
        )

    assert answer == "Your previous message was: My earlier question"


def test_agent_reports_when_there_is_no_previous_message():
    with patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch("app.agent.agent.save_chat_message"):
        answer = run_agent(
            question="What did I ask you previously?",
            conversation_id="test-no-previous-message",
            user_id=1,
        )

    assert answer == (
        "You have not asked a previous question in this conversation."
    )


def test_agent_skips_saved_copy_of_current_history_question():
    current_question = "What was my previous message?"
    previous_messages = [
        {"role": "user", "content": "My favorite color is blue"},
        {"role": "assistant", "content": "Got it."},
        {"role": "user", "content": current_question},
        {
            "role": "assistant",
            "content": "You have not asked a previous question.",
        },
    ]

    with patch(
        "app.agent.agent.load_chat_history",
        return_value=previous_messages,
    ), patch("app.agent.agent.save_chat_message"):
        answer = run_agent(
            question=current_question,
            conversation_id="test-repeated-history-question",
            user_id=1,
        )

    assert answer == (
        "Your previous message was: My favorite color is blue"
    )


def test_agent_ignores_current_prompt_when_it_is_the_only_saved_user_message():
    current_question = "What was my previous message?"

    with patch(
        "app.agent.agent.load_chat_history",
        return_value=[{"role": "user", "content": current_question}],
    ), patch("app.agent.agent.save_chat_message"):
        answer = run_agent(
            question=current_question,
            conversation_id="test-current-prompt-only",
            user_id=1,
        )

    assert answer == (
        "You have not asked a previous question in this conversation."
    )


def test_agent_reads_previous_message_from_saved_conversation():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Conversation.__table__.create(bind=engine)
    ConversationMessage.__table__.create(bind=engine)
    AuditLog.__table__.create(bind=engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    db.add(Conversation(
        conversation_id="test-saved-previous-message",
        user_id=1,
    ))
    db.add(Conversation(
        conversation_id="test-empty-previous-message",
        user_id=1,
    ))
    db.commit()
    db.close()

    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        SimpleNamespace(
            message=SimpleNamespace(content="Got it.", tool_calls=[])
        ),
        SimpleNamespace(
            message=SimpleNamespace(content="Noted.", tool_calls=[])
        ),
    ]

    try:
        with patch(
            "app.agent.agent.get_client",
            return_value=fake_client,
        ), patch("app.agent.agent.SessionLocal", session_factory):
            first_answer = run_agent(
                question="My favorite color is blue",
                conversation_id="test-saved-previous-message",
                user_id=1,
            )
            second_answer = run_agent(
                question="What was my previous message?",
                conversation_id="test-saved-previous-message",
                user_id=1,
            )
            third_answer = run_agent(
                question="I am learning Python",
                conversation_id="test-saved-previous-message",
                user_id=1,
            )
            fourth_answer = run_agent(
                question="What was my previous message?",
                conversation_id="test-saved-previous-message",
                user_id=1,
            )
            no_previous_answer = run_agent(
                question="What was my previous message?",
                conversation_id="test-empty-previous-message",
                user_id=1,
            )
            history = load_chat_history(
                "test-saved-previous-message",
                user_id=1,
            )

        assert first_answer == "Got it."
        assert second_answer == (
            "Your previous message was: My favorite color is blue"
        )
        assert third_answer == "Noted."
        assert fourth_answer == (
            "Your previous message was: I am learning Python"
        )
        assert no_previous_answer == (
            "You have not asked a previous question in this conversation."
        )
        assert fake_client.chat.call_count == 2

        third_request_messages = fake_client.chat.call_args_list[1].kwargs[
            "messages"
        ]
        assert [
            message["content"]
            for message in third_request_messages
            if message["role"] == "user"
        ] == [
            "My favorite color is blue",
            "What was my previous message?",
            "I am learning Python",
        ]

        assert history == [
            {"role": "user", "content": "My favorite color is blue"},
            {"role": "assistant", "content": "Got it."},
            {"role": "user", "content": "What was my previous message?"},
            {
                "role": "assistant",
                "content": "Your previous message was: My favorite color is blue",
            },
            {"role": "user", "content": "I am learning Python"},
            {"role": "assistant", "content": "Noted."},
            {"role": "user", "content": "What was my previous message?"},
            {
                "role": "assistant",
                "content": "Your previous message was: I am learning Python",
            },
        ]
    finally:
        engine.dispose()




def test_agent_handles_invalid_json_tool_arguments():
    fake_client = MagicMock()

    tool_call = SimpleNamespace(
        id="call-invalid-json",
        function=SimpleNamespace(
            name="search_document_content",
            arguments="{invalid json",
        ),
    )

    fake_client.chat.side_effect = [
        SimpleNamespace(
            message=SimpleNamespace(
                content=None,
                tool_calls=[tool_call],
            )
        ),
        SimpleNamespace(
            message=SimpleNamespace(
                content="Here is the answer.",
                tool_calls=[],
            )
        ),
    ]

    with patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ), patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch(
        "app.agent.agent.save_chat_message",
    ), patch(
        "app.agent.agent.save_audit_log",
    ), patch(
        "app.agent.agent.search_document_content",
        return_value={"result": "Found"},
    ) as mock_search:
        answer = run_agent(
            question="Find this information",
            conversation_id="test-invalid-json",
            user_id=1,
        )

    assert answer == "Here is the answer."
    mock_search.assert_called_once_with(
        "Find this information",
        user_id=1,
    )


def test_agent_rejects_unsupported_tool():
    fake_client = MagicMock()
    tool_call = SimpleNamespace(
        id="call-unsupported",
        function=SimpleNamespace(
            name="delete_document",
            arguments="{}",
        ),
    )
    fake_client.chat.return_value = SimpleNamespace(
        message=SimpleNamespace(
            content=None,
            tool_calls=[tool_call],
        )
    )

    with patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ), patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch(
        "app.agent.agent.save_chat_message",
    ):
        with pytest.raises(
            ValueError,
            match="Unsupported agent tool: delete_document",
        ):
            run_agent(
                question="Delete a document",
                conversation_id="test-unsupported-tool",
                user_id=1,
            )


def test_agent_handles_search_tool_value_error():
    fake_client = MagicMock()
    tool_call = SimpleNamespace(
        id="call-value-error",
        function=SimpleNamespace(
            name="search_document_content",
            arguments={"question": "Find document"},
        ),
    )
    fake_client.chat.side_effect = [
        SimpleNamespace(
            message=SimpleNamespace(
                content=None,
                tool_calls=[tool_call],
            )
        ),
        SimpleNamespace(
            message=SimpleNamespace(
                content="Search could not be completed.",
                tool_calls=[],
            )
        ),
    ]

    with patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ), patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch(
        "app.agent.agent.save_chat_message",
    ), patch(
        "app.agent.agent.save_audit_log",
    ), patch(
        "app.agent.agent.search_document_content",
        side_effect=ValueError("Invalid search input"),
    ):
        answer = run_agent(
            question="Find document",
            conversation_id="test-invalid-search",
            user_id=1,
        )

    assert answer == "Search could not be completed."


def test_agent_stops_after_five_tool_call_rounds():
    fake_client = MagicMock()

    tool_call = SimpleNamespace(
        id="call-repeat",
        function=SimpleNamespace(
            name="search_document_content",
            arguments={"question": "Search again"},
        ),
    )
    tool_response = SimpleNamespace(
        message=SimpleNamespace(
            content=None,
            tool_calls=[tool_call],
        )
    )
    fake_client.chat.return_value = tool_response

    with patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ), patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch(
        "app.agent.agent.save_chat_message",
    ), patch(
        "app.agent.agent.search_document_content",
        return_value={"result": "No final response yet"},
    ) as mock_search, patch(
        "app.agent.agent.save_audit_log",
    ) as mock_audit:
        with pytest.raises(
            RuntimeError,
            match="maximum number of tool-call rounds",
        ):
            run_agent(
                question="Search again",
                conversation_id="test-max-tool-rounds",
                user_id=1,
            )

    assert fake_client.chat.call_count == 5
    assert mock_search.call_count == 5
    mock_audit.assert_called_once_with(
        user_id=1,
        action="chat_request",
        status="failure",
        details="Ollama exceeded the maximum number of tool-call rounds.",
    )
    
def test_save_chat_message_rejects_invalid_role():
    with pytest.raises(ValueError, match="Invalid message role"):
        save_chat_message("test-conversation", "system", "Not allowed")


def test_load_chat_history_raises_when_conversation_missing():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Conversation.__table__.create(bind=engine)
    session_factory = sessionmaker(bind=engine)

    try:
        with patch("app.agent.agent.SessionLocal", session_factory):
            with pytest.raises(
                ValueError,
                match="Conversation not found",
            ):
                load_chat_history("missing-conversation", user_id=1)
    finally:
        engine.dispose()


def test_create_conversation_returns_saved_id():
    with patch(
        "app.agent.agent.save_conversation"
    ) as mock_save:
        conversation_id = create_conversation(user_id=1)

    assert isinstance(conversation_id, str)
    assert len(conversation_id) == 36
    mock_save.assert_called_once_with(conversation_id, 1)


def test_save_conversation_rolls_back_on_error():
    fake_db = MagicMock()
    fake_db.commit.side_effect = RuntimeError("Database error")

    with patch(
        "app.agent.agent.ensure_conversation_schema"
    ), patch(
        "app.agent.agent.SessionLocal",
        return_value=fake_db,
    ):
        with pytest.raises(RuntimeError, match="Database error"):
            save_conversation("test-conversation", user_id=1)

    fake_db.rollback.assert_called_once()
    fake_db.close.assert_called_once()
    

def test_agent_logs_failure_when_ollama_request_fails():
    fake_client = MagicMock()
    fake_client.chat.side_effect = RuntimeError("Ollama unavailable")

    with patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ), patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch(
        "app.agent.agent.save_chat_message",
    ), patch(
        "app.agent.agent.save_audit_log",
    ) as mock_audit:
        with pytest.raises(RuntimeError, match="Ollama unavailable"):
            run_agent(
                question="Find document information",
                conversation_id="test-ollama-failure",
                user_id=1,
            )

    mock_audit.assert_called_once_with(
        user_id=1,
        action="chat_request",
        status="failure",
        details="Ollama chat request failed.",
    )


def test_agent_reraises_ollama_error_when_failure_audit_also_fails():
    fake_client = MagicMock()
    fake_client.chat.side_effect = RuntimeError("Ollama unavailable")

    with patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ), patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch(
        "app.agent.agent.save_chat_message",
    ), patch(
        "app.agent.agent.save_audit_log",
        side_effect=RuntimeError("Audit database unavailable"),
    ) as mock_audit:
        with pytest.raises(RuntimeError, match="Ollama unavailable"):
            run_agent(
                question="Find document information",
                conversation_id="test-audit-failure",
                user_id=1,
            )

    mock_audit.assert_called_once()


def test_agent_returns_empty_string_when_model_content_is_none():
    fake_client = MagicMock()
    fake_client.chat.return_value = SimpleNamespace(
        message=SimpleNamespace(content=None, tool_calls=[])
    )

    with patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ), patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch(
        "app.agent.agent.save_chat_message",
    ), patch(
        "app.agent.agent.save_audit_log",
    ):
        answer = run_agent(
            question="Give me an answer",
            conversation_id="test-empty-answer",
            user_id=1,
        )

    assert answer == ""


def test_save_chat_message_rolls_back_when_commit_fails():
    fake_db = MagicMock()
    fake_db.commit.side_effect = RuntimeError("Database commit failed")

    with patch(
        "app.agent.agent.SessionLocal",
        return_value=fake_db,
    ):
        with pytest.raises(RuntimeError, match="Database commit failed"):
            save_chat_message(
                "test-save-failure",
                "user",
                "Hello",
            )

    fake_db.rollback.assert_called_once()
    fake_db.close.assert_called_once()


def test_save_audit_log_rolls_back_when_commit_fails():
    fake_db = MagicMock()
    fake_db.commit.side_effect = RuntimeError("Audit commit failed")

    with patch(
        "app.agent.agent.SessionLocal",
        return_value=fake_db,
    ):
        with pytest.raises(RuntimeError, match="Audit commit failed"):
            save_audit_log(
                user_id=1,
                action="chat_request",
                status="failure",
                details="Test failure",
            )

    fake_db.rollback.assert_called_once()
    fake_db.close.assert_called_once()
    
def test_agent_uses_fallback_when_model_dump_is_unavailable():
    tool_call = SimpleNamespace(
        id="call-fallback",
        function=SimpleNamespace(
            name="search_document_content",
            arguments={"question": "Find document details"},
        ),
    )

    # SimpleNamespace does not provide model_dump().
    tool_response = SimpleNamespace(
        message=SimpleNamespace(
            content=None,
            tool_calls=[tool_call],
        )
    )

    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        tool_response,
        SimpleNamespace(
            message=SimpleNamespace(
                content="Document details found.",
                tool_calls=[],
            )
        ),
    ]

    with patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ), patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch(
        "app.agent.agent.save_chat_message",
    ), patch(
        "app.agent.agent.save_audit_log",
    ), patch(
        "app.agent.agent.search_document_content",
        return_value={"result": "Found"},
    ):
        answer = run_agent(
            question="Find document details",
            conversation_id="test-model-dump-fallback",
            user_id=1,
        )

    assert answer == "Document details found."
    assert fake_client.chat.call_count == 2
    
def test_agent_uses_model_dump_when_available():
    tool_call = SimpleNamespace(
        id="call-model-dump",
        function=SimpleNamespace(
            name="search_document_content",
            arguments={"question": "Find document details"},
        ),
    )

    model_dump = MagicMock(
        return_value={
            "role": "assistant",
            "tool_calls": [{"id": "call-model-dump"}],
        }
    )

    assistant_message = SimpleNamespace(
        content=None,
        tool_calls=[tool_call],
        model_dump=model_dump,
    )

    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        SimpleNamespace(message=assistant_message),
        SimpleNamespace(
            message=SimpleNamespace(
                content="Document details found.",
                tool_calls=[],
            )
        ),
    ]

    with patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ), patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch(
        "app.agent.agent.save_chat_message",
    ), patch(
        "app.agent.agent.save_audit_log",
    ), patch(
        "app.agent.agent.search_document_content",
        return_value={"result": "Found"},
    ):
        answer = run_agent(
            question="Find document details",
            conversation_id="test-model-dump",
            user_id=1,
        )

    assert answer == "Document details found."
    model_dump.assert_called_once_with(exclude_none=True)
    assert fake_client.chat.call_count == 2

@pytest.mark.parametrize(
    "question,user_id",
    [
        (123, 1),
        ("   ", 1),
        ("a" * 1001, 1),
        ("hello", 0),
        ("hello", -1),
        ("hello", "1"),
    ],
)
def test_search_document_content_rejects_invalid_input(question, user_id):
    with pytest.raises(ValueError):
        search_document_content(question, user_id)


def test_search_document_content_returns_formatted_results():
    mock_results = [
        SimpleNamespace(document_id="doc-1", chunk_text="Restaurant opens at 9 AM."),
        SimpleNamespace(document_id="doc-2", chunk_text="Restaurant closes at 10 PM."),
    ]

    with patch(
        "app.agent.tools.retrieve_relevant_chunks",
        return_value=mock_results,
    ) as mock_retrieve:
        result = search_document_content(
            "  When does the restaurant open?  ",
            user_id=1,
        )

    assert result == [
        {
            "document_id": "doc-1",
            "chunk": "Restaurant opens at 9 AM.",
        },
        {
            "document_id": "doc-2",
            "chunk": "Restaurant closes at 10 PM.",
        },
    ]

    mock_retrieve.assert_called_once_with(
        "When does the restaurant open?",
        user_id=1,
        limit=3,
    )
def test_search_document_content_runs():
    with patch(
        "app.agent.tools.retrieve_relevant_chunks",
        return_value=[
            SimpleNamespace(
                document_id="doc-1",
                chunk_text="Restaurant opens at 9 AM.",
            )
        ],
    ) as mock_retrieve:
        result = search_document_content("hello", user_id=1)

    assert result == [
        {
            "document_id": "doc-1",
            "chunk": "Restaurant opens at 9 AM.",
        }
    ]
    mock_retrieve.assert_called_once_with("hello", user_id=1, limit=3)
def test_create_embedding_raises_error_when_dimension_mismatches():
    fake_embedding = [0.1, 0.2, 0.3]

    with patch.dict(
        "os.environ",
        {
            "OLLAMA_EMBEDDING_MODEL": "test-model",
            "PGVECTOR_DIMENSION": "384",
        },
    ), patch(
        "app.rag.embeddings.client.embed",
        return_value={"embeddings": [fake_embedding]},
    ):
        with pytest.raises(
            ValueError,
            match="Embedding dimension mismatch",
        ):
            create_embedding("test input")


def test_create_embedding_returns_embedding_when_dimension_matches():
    fake_embedding = [0.1, 0.2, 0.3]

    with patch.dict(
        "os.environ",
        {
            "OLLAMA_EMBEDDING_MODEL": "test-model",
            "PGVECTOR_DIMENSION": "3",
        },
    ), patch(
        "app.rag.embeddings.client.embed",
        return_value={"embeddings": [fake_embedding]},
    ) as mock_embed:
        result = create_embedding("test input")

    assert result == fake_embedding
    mock_embed.assert_called_once_with(
        model="test-model",
        input="test input",
        dimensions=3,
    )
def test_agent_handles_business_tool_value_error():
    fake_client = MagicMock()

    tool_call = SimpleNamespace(
        id="call-business-value-error",
        function=SimpleNamespace(
            name="query_business_data",
            arguments={"action": "document_count"},
        ),
    )

    fake_client.chat.side_effect = [
        SimpleNamespace(
            message=SimpleNamespace(
                content=None,
                tool_calls=[tool_call],
            )
        ),
        SimpleNamespace(
            message=SimpleNamespace(
                content="Business data could not be retrieved.",
                tool_calls=[],
            )
        ),
    ]

    with patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ), patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch(
        "app.agent.agent.save_chat_message",
    ), patch(
        "app.agent.agent.save_audit_log",
    ), patch(
        "app.agent.agent.query_business_data",
        side_effect=ValueError("Invalid action"),
    ):
        answer = run_agent(
            question="How many documents do I have?",
            conversation_id="test-business-value-error",
            user_id=1,
        )

    assert answer == "Business data could not be retrieved."
    assert fake_client.chat.call_count == 2


def test_agent_handles_business_tool_general_exception():
    fake_client = MagicMock()

    tool_call = SimpleNamespace(
        id="call-business-error",
        function=SimpleNamespace(
            name="query_business_data",
            arguments={"action": "document_count"},
        ),
    )

    fake_client.chat.side_effect = [
        SimpleNamespace(
            message=SimpleNamespace(
                content=None,
                tool_calls=[tool_call],
            )
        ),
        SimpleNamespace(
            message=SimpleNamespace(
                content="Business data is temporarily unavailable.",
                tool_calls=[],
            )
        ),
    ]

    with patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ), patch(
        "app.agent.agent.load_chat_history",
        return_value=[],
    ), patch(
        "app.agent.agent.save_chat_message",
    ), patch(
        "app.agent.agent.save_audit_log",
    ), patch(
        "app.agent.agent.query_business_data",
        side_effect=RuntimeError("Database connection failed"),
    ):
        answer = run_agent(
            question="How many documents do I have?",
            conversation_id="test-business-general-error",
            user_id=1,
        )

    assert answer == "Business data is temporarily unavailable."
    assert fake_client.chat.call_count == 2