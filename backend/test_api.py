
from types import SimpleNamespace
from fastapi import HTTPException
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.main import app
from app.api import auth as auth_api
from app.api.dependencies import get_current_user, get_db
from app.database.models import AuditLog, Conversation, ConversationMessage
from io import BytesIO
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

client = TestClient(app)


@pytest.fixture
def authenticated_api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Conversation.__table__.create(bind=engine)
    ConversationMessage.__table__.create(bind=engine)
    AuditLog.__table__.create(bind=engine)
    db = sessionmaker(bind=engine)()
    previous_overrides = app.dependency_overrides.copy()

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[get_db] = lambda: db

    try:
        yield client, db
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        db.close()
        engine.dispose()


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    
def test_chat_rejects_empty_question(authenticated_api):
    response = authenticated_api[0].post(
        "/chat/",
        json={"question": ""}
    )

    assert response.status_code == 422


from unittest.mock import patch


def test_chat_returns_answer(authenticated_api):
    with patch(
        "app.api.chat.retrieve_relevant_chunks",
        return_value=[]
    ), patch(
        "app.api.chat.create_conversation",
        return_value="new-chat-conversation",
    ) as create_chat_conversation:
        response = authenticated_api[0].post(
            "/chat/",
            json={"question": "When does the restaurant open?"}
        )

    assert response.status_code == 200
    assert response.json() == {
        "question": "When does the restaurant open?",
        "answer": "I couldn't find relevant information in the uploaded documents.",
        "conversation_id": "new-chat-conversation",
    }
    create_chat_conversation.assert_called_once_with(1)


def test_chat_rejects_overlong_question(authenticated_api):
    response = authenticated_api[0].post(
        "/chat/",
        json={"question": "a" * 1001}
    )

    assert response.status_code == 422


def test_agent_chat_openapi_documents_conversation_id():
    operation = app.openapi()["paths"]["/chat/agent"]["post"]
    schemas = app.openapi()["components"]["schemas"]

    request_schema = schemas["AgentChatRequest"]["properties"]
    response_schema = schemas["ChatResponse"]["properties"]

    assert "conversation_id" in request_schema
    assert "conversation_id" in response_schema


def test_regular_chat_openapi_documents_conversation_id():
    operation = app.openapi()["paths"]["/chat/"]["post"]
    schemas = app.openapi()["components"]["schemas"]
    request_schema = schemas["ChatRequest"]["properties"]
    response_schema = schemas["ChatResponse"]["properties"]

    assert "conversation_id" in request_schema
    assert "conversation_id" in response_schema


def test_regular_chat_continues_owned_conversation(authenticated_api):
    api_client, db = authenticated_api
    db.add(Conversation(
        conversation_id="regular-chat-conversation",
        user_id=1,
    ))
    db.commit()

    with patch("app.api.chat.retrieve_relevant_chunks", return_value=[]), patch(
        "app.api.chat.create_conversation",
    ) as create_chat_conversation:
        response = api_client.post(
            "/chat/",
            json={
                "question": "Follow-up",
                "conversation_id": "regular-chat-conversation",
            },
        )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "regular-chat-conversation"
    create_chat_conversation.assert_not_called()


def test_regular_chat_history_is_available_to_agent_chat(authenticated_api):
    api_client, db = authenticated_api
    conversation_id = "cross-endpoint-conversation"
    db.add(Conversation(conversation_id=conversation_id, user_id=1))
    db.commit()
    agent_session_factory = sessionmaker(bind=db.get_bind())

    with patch(
        "app.api.chat.retrieve_relevant_chunks",
        return_value=[SimpleNamespace(chunk_text="2 + 3 = 5")],
    ), patch(
        "app.api.chat.generate_answer",
        return_value="The sum of 2 and 3 is 5.",
    ), patch(
        "app.agent.agent.SessionLocal",
        agent_session_factory,
    ), patch(
        "app.agent.agent.get_client",
        return_value=MagicMock(),
    ):
        first_response = api_client.post(
            "/chat/",
            json={
                "question": "what sum of 2 and 3 is?",
                "conversation_id": conversation_id,
            },
        )
        follow_up_response = api_client.post(
            "/chat/agent",
            json={
                "question": "what i ask from previous message",
                "conversation_id": conversation_id,
            },
        )

    assert first_response.status_code == 200
    assert first_response.json()["answer"] == "The sum of 2 and 3 is 5."
    assert follow_up_response.status_code == 200
    assert follow_up_response.json()["answer"] == (
        "Your previous message was: what sum of 2 and 3 is?"
    )


def test_regular_chat_rejects_another_users_conversation(authenticated_api):
    api_client, db = authenticated_api
    db.add(Conversation(
        conversation_id="another-users-chat",
        user_id=2,
    ))
    db.commit()

    with patch("app.api.chat.retrieve_relevant_chunks") as retrieve_chunks:
        response = api_client.post(
            "/chat/",
            json={
                "question": "Do not access this conversation",
                "conversation_id": "another-users-chat",
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."
    retrieve_chunks.assert_not_called()


def test_agent_chat_creates_and_continues_conversation(authenticated_api):
    api_client, db = authenticated_api
    answers = ["First answer", "Follow-up answer"]

    with patch("app.agent.agent.ensure_conversation_schema"), patch(
        "app.agent.agent.SessionLocal",
        return_value=db,
    ), patch("app.api.chat.run_agent", side_effect=answers) as run_agent:
        first_response = api_client.post(
            "/chat/agent",
            json={"question": "First question"},
        )

        assert first_response.status_code == 200
        first_body = first_response.json()
        conversation_id = first_body["conversation_id"]

        assert conversation_id
        assert first_body == {
            "question": "First question",
            "answer": "First answer",
            "conversation_id": conversation_id,
        }
        saved_conversation = db.query(Conversation).filter(
            Conversation.conversation_id == conversation_id,
        ).first()
        assert saved_conversation is not None
        assert saved_conversation.user_id == 1

        follow_up_response = api_client.post(
            "/chat/agent",
            json={
                "question": "Follow-up question",
                "conversation_id": conversation_id,
            },
        )

    assert follow_up_response.status_code == 200
    assert follow_up_response.json()["conversation_id"] == conversation_id
    assert run_agent.call_count == 2
    assert run_agent.call_args_list[0].kwargs["conversation_id"] == conversation_id
    assert run_agent.call_args_list[1].kwargs["conversation_id"] == conversation_id
    assert all(call.kwargs["user_id"] == 1 for call in run_agent.call_args_list)


def test_agent_chat_returns_previous_user_message(authenticated_api):
    api_client, db = authenticated_api
    agent_session_factory = sessionmaker(bind=db.get_bind())
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        SimpleNamespace(
            message=SimpleNamespace(content="Understood.", tool_calls=[])
        ),
        SimpleNamespace(
            message=SimpleNamespace(content="Noted.", tool_calls=[])
        ),
    ]

    with patch("app.agent.agent.ensure_conversation_schema"), patch(
        "app.agent.agent.SessionLocal",
        agent_session_factory,
    ), patch(
        "app.agent.agent.get_client",
        return_value=fake_client,
    ):
        first_response = api_client.post(
            "/chat/agent",
            json={"question": "My favorite color is blue"},
        )
        conversation_id = first_response.json()["conversation_id"]

        second_response = api_client.post(
            "/chat/agent",
            json={
                "question": "What was my previous message?",
                "conversation_id": conversation_id,
            },
        )
        third_response = api_client.post(
            "/chat/agent",
            json={
                "question": "I am learning Python",
                "conversation_id": conversation_id,
            },
        )
        fourth_response = api_client.post(
            "/chat/agent",
            json={
                "question": "What was my previous message?",
                "conversation_id": conversation_id,
            },
        )
        empty_conversation_response = api_client.post(
            "/chat/agent",
            json={"question": "What was my previous message?"},
        )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["answer"] == (
        "Your previous message was: My favorite color is blue"
    )
    assert third_response.status_code == 200
    assert fourth_response.status_code == 200
    assert fourth_response.json()["answer"] == (
        "Your previous message was: I am learning Python"
    )
    assert fourth_response.json()["conversation_id"] == conversation_id
    assert empty_conversation_response.status_code == 200
    assert empty_conversation_response.json()["answer"] == (
        "You have not asked a previous question in this conversation."
    )
    assert fake_client.chat.call_count == 2


def test_agent_chat_allows_conversation_owned_by_current_user(authenticated_api):
    api_client, db = authenticated_api
    conversation = Conversation(
        conversation_id="owned-conversation",
        user_id=1,
    )
    db.add(conversation)
    db.commit()

    with patch(
        "app.api.chat.run_agent",
        return_value="Conversation continued.",
    ) as run_agent:
        response = api_client.post(
            "/chat/agent",
            json={
                "question": "Continue",
                "conversation_id": "owned-conversation",
            },
        )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "owned-conversation"
    run_agent.assert_called_once_with(
        question="Continue",
        conversation_id="owned-conversation",
        user_id=1,
    )


def test_agent_chat_rejects_another_users_conversation(authenticated_api):
    api_client, db = authenticated_api
    db.add(Conversation(
        conversation_id="other-users-conversation",
        user_id=2,
    ))
    db.commit()

    with patch("app.api.chat.run_agent") as run_agent:
        response = api_client.post(
            "/chat/agent",
            json={
                "question": "Try to access",
                "conversation_id": "other-users-conversation",
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."
    run_agent.assert_not_called()


def test_agent_chat_rejects_missing_and_empty_conversation_ids(authenticated_api):
    api_client, _ = authenticated_api

    missing = api_client.post(
        "/chat/agent",
        json={"question": "Unknown conversation", "conversation_id": "missing"},
    )
    empty = api_client.post(
        "/chat/agent",
        json={"question": "Empty conversation", "conversation_id": "   "},
    )

    assert missing.status_code == 404
    assert empty.status_code == 422


def test_agent_chat_returns_safe_error_when_database_fails(authenticated_api):
    api_client, db = authenticated_api
    with patch.object(db, "query", side_effect=SQLAlchemyError("database detail")):
        response = api_client.post(
            "/chat/agent",
            json={
                "question": "Continue",
                "conversation_id": "existing-conversation",
            },
        )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Conversation service is temporarily unavailable."
    )
    assert "database detail" not in response.text


def test_agent_chat_returns_safe_error_when_saving_conversation_fails(
    authenticated_api,
):
    api_client, _ = authenticated_api
    with patch(
        "app.api.chat.create_conversation",
        side_effect=SQLAlchemyError("database detail"),
    ):
        response = api_client.post(
            "/chat/agent",
            json={"question": "Start a conversation"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Conversation service is temporarily unavailable."
    )
    assert "database detail" not in response.text


def test_upload_rejects_non_pdf(authenticated_api):
    response = authenticated_api[0].post(
        "/documents/upload",
        files={
            "file": (
                "notes.txt",
                BytesIO(b"hello"),
                "text/plain"
            )
        }
    )

    assert response.status_code == 400


def test_upload_rejects_fake_pdf(authenticated_api):
    response = authenticated_api[0].post(
        "/documents/upload",
        files={
            "file": (
                "fake.pdf",
                BytesIO(b"This is not a PDF"),
                "application/pdf"
            )
        }
    )

    assert response.status_code == 400


def test_upload_rejects_overlarge_pdf(authenticated_api):
    large_content = b"%PDF-" + b"a" * (10 * 1024 * 1024)

    response = authenticated_api[0].post(
        "/documents/upload",
        files={
            "file": (
                "large.pdf",
                BytesIO(large_content),
                "application/pdf"
            )
        }
    )

    assert response.status_code == 413
    
def test_upload_valid_pdf_success(authenticated_api, monkeypatch, tmp_path):
    from pathlib import Path
    from app.api import documents

    client, db = authenticated_api
    fake_file_path = tmp_path / "test.pdf"

    class FakeDocument:
        id = 123
        filename = "test.pdf"
        file_path = str(fake_file_path)
        user_id = 1

    fake_document = FakeDocument()

    class FakeDB:
        def add(self, obj):
            pass

        def commit(self):
            pass

        def refresh(self, obj):
            pass

        def rollback(self):
            pass

        def delete(self, obj):
            pass

        def close(self):
            pass

        def query(self, model):
            return self

        def filter(self, *args, **kwargs):
            return self

        def delete(self, **kwargs):
            return 0

    fake_db = FakeDB()
    monkeypatch.setattr(documents, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(documents, "extract_text_from_pdf", lambda path: "Restaurant opening hours")
    monkeypatch.setattr(documents, "validate_extracted_text", lambda text: text)
    monkeypatch.setattr(documents, "process_document", lambda document_id, text: None)

    # Make Document(...) return our fake object
    monkeypatch.setattr(documents, "Document", lambda **kwargs: fake_document)

    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "test.pdf",
                b"%PDF-1.4 fake test content",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["document_id"] == 123
    assert response.json()["filename"] == "test.pdf"


def test_upload_rejects_pdf_when_text_extraction_fails(
    authenticated_api, monkeypatch, tmp_path
):
    from app.api import documents

    client, _ = authenticated_api

    monkeypatch.setattr(documents, "upload_dir", tmp_path)
    monkeypatch.setattr(
        documents,
        "extract_text_from_pdf",
        lambda path: (_ for _ in ()).throw(
            ValueError("Could not extract PDF text")
        ),
    )

    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "broken.pdf",
                b"%PDF-1.4 fake test content",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Could not extract PDF text"
    assert list(tmp_path.iterdir()) == []
    
def test_upload_cleans_up_when_processing_fails(
    authenticated_api, monkeypatch, tmp_path
):
    from app.api import documents

    client, _ = authenticated_api
    monkeypatch.setattr(documents, "upload_dir", tmp_path)

    class FakeDocument:
        id = 123
        filename = "test.pdf"
        file_path = ""
        user_id = 1

    fake_document = FakeDocument()
    deleted_documents = []

    class FakeDB:
        def add(self, obj):
            pass

        def commit(self):
            pass

        def refresh(self, obj):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

        def query(self, model):
            return self

        def filter(self, *args, **kwargs):
            return self

        def delete(self, obj=None, **kwargs):
            if obj is not None:
                deleted_documents.append(obj)
            return 0

    fake_db = FakeDB()

    monkeypatch.setattr(documents, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(
        documents, "Document", lambda **kwargs: fake_document
    )
    monkeypatch.setattr(
        documents, "extract_text_from_pdf", lambda path: "Some text"
    )
    monkeypatch.setattr(
        documents, "validate_extracted_text", lambda text: text
    )
    monkeypatch.setattr(
        documents,
        "process_document",
        lambda document_id, text: (_ for _ in ()).throw(
            RuntimeError("Processing failed")
        ),
    )

    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "test.pdf",
                b"%PDF-1.4 fake test content",
                "application/pdf",
            )
        },
    )
     
    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Could not upload and process the document."
    )
    assert fake_document in deleted_documents
    assert list(tmp_path.iterdir()) == []
def test_register_user_success(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.refresh.side_effect = lambda user: setattr(user, "id", 1)

    app.dependency_overrides[auth_api.get_db] = lambda: db
    monkeypatch.setattr(auth_api, "hash_password", lambda password: "hashed-password")

    client = TestClient(app)
    try:
        response = client.post(
            "/auth/register",
            json={"email": "TEST@example.com", "password": "StrongPass123"},
        )

        assert response.status_code == 201
        assert response.json()["email"] == "test@example.com"
        assert response.json()["id"] == 1
        db.add.assert_called_once()
        db.commit.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_register_user_rejects_existing_email():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        id=1, email="test@example.com"
    )

    app.dependency_overrides[auth_api.get_db] = lambda: db
    client = TestClient(app)
    try:
        response = client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "StrongPass123"},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "Email is already registered."
    finally:
        app.dependency_overrides.clear()


def test_login_rejects_invalid_credentials(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[auth_api.get_db] = lambda: db
    client = TestClient(app)
    try:
        response = client.post(
            "/auth/login",
            json={"email": "missing@example.com", "password": "WrongPass123"},
        )

        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
    finally:
        app.dependency_overrides.clear()


def test_read_current_user_returns_user():
    user = SimpleNamespace(id=7, email="test@example.com")
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app)
    try:
        response = client.get("/auth/me")

        assert response.status_code == 200
        assert response.json() == {"id": 7, "email": "test@example.com"}
    finally:
        app.dependency_overrides.clear()


def test_get_db_yields_session_and_closes_it(monkeypatch):
    mock_db = MagicMock()
    monkeypatch.setattr(auth_api, "SessionLocal", lambda: mock_db)

    db_generator = auth_api.get_db()

    assert next(db_generator) is mock_db

    with pytest.raises(StopIteration):
        next(db_generator)

    mock_db.close.assert_called_once()


def test_get_db_closes_session_when_generator_closes(monkeypatch):
    mock_db = MagicMock()
    monkeypatch.setattr(auth_api, "SessionLocal", lambda: mock_db)

    db_generator = auth_api.get_db()
    assert next(db_generator) is mock_db

    db_generator.close()

    mock_db.close.assert_called_once()


def test_register_user_rolls_back_when_commit_fails(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.commit.side_effect = Exception("Database error")

    app.dependency_overrides[auth_api.get_db] = lambda: db
    monkeypatch.setattr(auth_api, "hash_password", lambda password: "hashed")

    client = TestClient(app)
    try:
        response = client.post(
            "/auth/register",
            json={"email": "new@example.com", "password": "StrongPass123"},
        )

        assert db.commit.call_count == 1
        assert db.rollback.call_count == 1
        assert response.status_code == 500
        assert response.json()["detail"] == "Could not create user."
        db.rollback.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_login_success(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        id=5,
        email="test@example.com",
        hashed_password="hashed",
    )

    app.dependency_overrides[auth_api.get_db] = lambda: db
    monkeypatch.setattr(auth_api, "verify_password", lambda password, hashed: True)
    monkeypatch.setattr(auth_api, "create_access_token", lambda user_id: "test-token")

    client = TestClient(app)
    try:
        response = client.post(
            "/auth/login",
            json={"email": "TEST@example.com", "password": "StrongPass123"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "access_token": "test-token",
            "token_type": "bearer",
        }
    finally:
        app.dependency_overrides.clear()


def test_swagger_token_success(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        id=5,
        email="test@example.com",
        hashed_password="hashed",
    )

    app.dependency_overrides[auth_api.get_db] = lambda: db
    monkeypatch.setattr(auth_api, "verify_password", lambda password, hashed: True)
    monkeypatch.setattr(auth_api, "create_access_token", lambda user_id: "test-token")

    client = TestClient(app)
    try:
        response = client.post(
            "/auth/token",
            data={"username": " TEST@example.com ", "password": "StrongPass123"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "access_token": "test-token",
            "token_type": "bearer",
        }
    finally:
        app.dependency_overrides.clear()


def test_swagger_token_rejects_invalid_credentials(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        id=5,
        email="test@example.com",
        hashed_password="hashed",
    )

    app.dependency_overrides[auth_api.get_db] = lambda: db
    monkeypatch.setattr(
        auth_api, "verify_password", lambda password, hashed: False
    )

    client = TestClient(app)
    try:
        response = client.post(
            "/auth/token",
            data={
                "username": "test@example.com",
                "password": "WrongPassword123",
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password."
        assert response.headers["www-authenticate"] == "Bearer"
    finally:
        app.dependency_overrides.clear()
        
def test_chat_rejects_whitespace_question(authenticated_api):
    response = authenticated_api[0].post(
        "/chat/",
        json={"question": "   "},
    )

    assert response.status_code == 422


def test_agent_chat_rejects_whitespace_question(authenticated_api):
    response = authenticated_api[0].post(
        "/chat/agent",
        json={"question": "   "},
    )

    assert response.status_code == 422


def test_regular_chat_accepts_explicit_null_conversation_id(authenticated_api):
    api_client, _ = authenticated_api

    with patch(
        "app.api.chat.create_conversation",
        return_value="new-conversation",
    ) as create_chat_conversation, patch(
        "app.api.chat.retrieve_relevant_chunks",
        return_value=[],
    ):
        response = api_client.post(
            "/chat/",
            json={"question": "Hello", "conversation_id": None},
        )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "new-conversation"
    create_chat_conversation.assert_called_once_with(1)


def test_agent_chat_accepts_explicit_null_conversation_id(authenticated_api):
    api_client, _ = authenticated_api

    with patch(
        "app.api.chat.create_conversation",
        return_value="new-conversation",
    ) as create_chat_conversation, patch(
        "app.api.chat.run_agent",
        return_value="Hello!",
    ) as run_agent:
        response = api_client.post(
            "/chat/agent",
            json={"question": "Hello", "conversation_id": None},
        )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "new-conversation"
    create_chat_conversation.assert_called_once_with(1)
    run_agent.assert_called_once_with(
        question="Hello",
        conversation_id="new-conversation",
        user_id=1,
    )


@pytest.mark.parametrize(
    "endpoint",
    ["/chat/", "/chat/agent"],
)
def test_chat_rejects_whitespace_conversation_id(
    authenticated_api,
    endpoint,
):
    response = authenticated_api[0].post(
        endpoint,
        json={
            "question": "Hello",
            "conversation_id": "   ",
        },
    )

    assert response.status_code == 422


def test_regular_chat_returns_503_when_conversation_lookup_fails(
    authenticated_api,
):
    api_client, db = authenticated_api

    with patch.object(
        db,
        "query",
        side_effect=SQLAlchemyError("Database details"),
    ):
        response = api_client.post(
            "/chat/",
            json={
                "question": "Hello",
                "conversation_id": "existing-conversation",
            },
        )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Conversation service is temporarily unavailable."
    )
    assert "Database details" not in response.text


def test_regular_chat_returns_503_when_creating_conversation_fails(
    authenticated_api,
):
    api_client, _ = authenticated_api

    with patch(
        "app.api.chat.create_conversation",
        side_effect=SQLAlchemyError("Database details"),
    ):
        response = api_client.post(
            "/chat/",
            json={"question": "Hello"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Conversation service is temporarily unavailable."
    )
    assert "Database details" not in response.text


def test_regular_chat_rolls_back_when_saving_messages_fails(
    authenticated_api,
):
    api_client, db = authenticated_api

    with patch(
        "app.api.chat.retrieve_relevant_chunks",
        return_value=[],
    ), patch.object(
        db,
        "commit",
        side_effect=SQLAlchemyError("Commit failed"),
    ), patch.object(db, "rollback", wraps=db.rollback) as mock_rollback:
        response = api_client.post(
            "/chat/",
            json={"question": "Hello"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Conversation service is temporarily unavailable."
    )
    mock_rollback.assert_called_once()
def test_regular_chat_generates_answer_from_relevant_chunks(authenticated_api):
    api_client, _ = authenticated_api

    chunks = [
        SimpleNamespace(chunk_text="The restaurant opens at 9 AM."),
        SimpleNamespace(chunk_text="The restaurant closes at 10 PM."),
    ]

    with patch(
        "app.api.chat.create_conversation",
        return_value="test-conversation",
    ), patch(
        "app.api.chat.retrieve_relevant_chunks",
        return_value=chunks,
    ), patch(
        "app.api.chat.generate_answer",
        return_value="The restaurant opens at 9 AM.",
    ) as mock_generate:
        response = api_client.post(
            "/chat/",
            json={"question": "When does the restaurant open?"},
        )

    assert response.status_code == 200
    assert response.json()["answer"] == "The restaurant opens at 9 AM."
    mock_generate.assert_called_once_with(
        "When does the restaurant open?",
        "The restaurant opens at 9 AM.\n\nThe restaurant closes at 10 PM.",
    )


def test_regular_chat_returns_404_for_missing_conversation(authenticated_api):
    api_client, _ = authenticated_api

    response = api_client.post(
        "/chat/",
        json={
            "question": "Hello",
            "conversation_id": "does-not-exist",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."
def test_upload_rejects_filename_without_pdf_extension(authenticated_api):
    response = authenticated_api[0].post(
        "/documents/upload",
        files={
            "file": (
                "notes.txt",
                b"%PDF-valid-content",
                "application/pdf"
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "The filename must end with .pdf."
def test_upload_http_exception_deletes_created_document(
    authenticated_api, tmp_path
):
    api_client, _ = authenticated_api
    fake_db = MagicMock()

    fake_document = SimpleNamespace(
        id=123,
        filename="notes.pdf",
        file_path=str(tmp_path / "notes.pdf"),
        user_id=1,
    )

    with patch("app.api.documents.upload_dir", tmp_path), \
         patch("app.api.documents.SessionLocal", return_value=fake_db), \
         patch("app.api.documents.extract_text_from_pdf", return_value="valid text"), \
         patch("app.api.documents.validate_extracted_text", return_value="valid text"), \
         patch("app.api.documents.Document", return_value=fake_document), \
         patch(
             "app.api.documents.process_document",
             side_effect=HTTPException(status_code=400, detail="forced")
         ):

        response = api_client.post(
            "/documents/upload",
            files={
                "file": (
                    "notes.pdf",
                    b"%PDF-valid-content",
                    "application/pdf"
                )
            },
        )

    assert response.status_code == 400
    fake_db.delete.assert_called_once_with(fake_document)
    assert fake_db.commit.call_count == 2
    fake_db.close.assert_called_once()
def test_upload_rolls_back_if_document_cleanup_fails(
    authenticated_api, tmp_path
):
    api_client, _ = authenticated_api
    fake_db = MagicMock()

    fake_document = SimpleNamespace(
        id=123,
        filename="notes.pdf",
        file_path=str(tmp_path / "notes.pdf"),
        user_id=1,
    )

    with patch("app.api.documents.upload_dir", tmp_path), \
         patch("app.api.documents.SessionLocal", return_value=fake_db), \
         patch("app.api.documents.extract_text_from_pdf", return_value="valid text"), \
         patch("app.api.documents.validate_extracted_text", return_value="valid text"), \
         patch("app.api.documents.Document", return_value=fake_document), \
         patch(
             "app.api.documents.process_document",
             side_effect=RuntimeError("processing failed")
         ), \
         patch.object(
             fake_db,
             "query",
             side_effect=RuntimeError("cleanup failed")
         ):

        response = api_client.post(
            "/documents/upload",
            files={
                "file": (
                    "notes.pdf",
                    b"%PDF-valid-content",
                    "application/pdf"
                )
            },
        )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Could not upload and process the document."
    )
    assert fake_db.rollback.call_count >= 2
    fake_db.close.assert_called_once()
def test_upload_http_exception_when_file_already_missing(
    authenticated_api, tmp_path
):
    api_client, _ = authenticated_api
    fake_db = MagicMock()

    fake_document = SimpleNamespace(
        id=123,
        filename="notes.pdf",
        file_path=str(tmp_path / "notes.pdf"),
        user_id=1,
    )

    def delete_file_then_raise(document_id, text):
        for uploaded_file in tmp_path.glob("*.pdf"):
            uploaded_file.unlink()

        raise HTTPException(status_code=400, detail="forced")

    with patch("app.api.documents.upload_dir", tmp_path), \
         patch("app.api.documents.SessionLocal", return_value=fake_db), \
         patch("app.api.documents.extract_text_from_pdf", return_value="valid text"), \
         patch("app.api.documents.validate_extracted_text", return_value="valid text"), \
         patch("app.api.documents.Document", return_value=fake_document), \
         patch(
             "app.api.documents.process_document",
             side_effect=delete_file_then_raise
         ):

        response = api_client.post(
            "/documents/upload",
            files={
                "file": (
                    "notes.pdf",
                    b"%PDF-valid-content",
                    "application/pdf"
                )
            },
        )

    assert response.status_code == 400
    assert fake_db.delete.call_count == 1
    assert fake_db.commit.call_count == 2
    assert list(tmp_path.iterdir()) == []
    fake_db.close.assert_called_once()


def test_upload_general_exception_when_document_and_file_missing(
    authenticated_api, monkeypatch, tmp_path
):
    from app.api import documents

    api_client, _ = authenticated_api
    fake_db = MagicMock()

    monkeypatch.setattr(documents, "upload_dir", tmp_path)
    monkeypatch.setattr(documents, "SessionLocal", lambda: fake_db)

    def delete_file_then_raise(path):
        for uploaded_file in tmp_path.glob("*.pdf"):
            uploaded_file.unlink()

        raise RuntimeError("Unexpected extraction error")

    monkeypatch.setattr(
        documents,
        "extract_text_from_pdf",
        delete_file_then_raise
    )

    response = api_client.post(
        "/documents/upload",
        files={
            "file": (
                "notes.pdf",
                b"%PDF-valid-content",
                "application/pdf"
            )
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Could not upload and process the document."
    )

    fake_db.rollback.assert_called_once()
    fake_db.delete.assert_not_called()
    fake_db.close.assert_called_once()
    assert list(tmp_path.iterdir()) == []