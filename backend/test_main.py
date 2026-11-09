
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app import main
import importlib
import sys


def test_health_returns_ok_when_database_is_ready():
    original_value = getattr(main.app.state, "db_ready", None)
    main.app.state.db_ready = True

    try:
        response = TestClient(main.app).get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    finally:
        if original_value is None:
            delattr(main.app.state, "db_ready")
        else:
            main.app.state.db_ready = original_value


def test_health_returns_degraded_when_database_is_unavailable():
    main.app.state.db_ready = False
    main.app.state.db_error = "Database connection failed"

    response = TestClient(main.app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "database": "unavailable",
    }


def test_health_uses_default_error_when_not_configured():
    if hasattr(main.app.state, "db_error"):
        delattr(main.app.state, "db_error")

    main.app.state.db_ready = False

    response = TestClient(main.app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "database": "unavailable",
    }


def test_db_test_returns_connected(monkeypatch):
    mock_engine = MagicMock()
    monkeypatch.setattr(main, "engine", mock_engine)

    response = TestClient(main.app).get("/db-test")

    assert response.status_code == 200
    assert response.json() == {"database": "connected"}
    mock_engine.connect.assert_called_once()


def test_db_test_returns_error(monkeypatch):
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = Exception("Connection failed")
    monkeypatch.setattr(main, "engine", mock_engine)

    response = TestClient(main.app).get("/db-test")

    assert response.status_code == 200
    assert response.json() == {"database": "error"}

def test_startup_database_failure_sets_degraded_state(monkeypatch):
    import app.database.connection as db_connection

    monkeypatch.setattr(
        db_connection,
        "ensure_pgvector_extension",
        lambda: (_ for _ in ()).throw(Exception("Database unavailable")),
    )

    monkeypatch.setattr(
        db_connection,
        "ensure_conversation_messages_schema",
        lambda: None,
    )

    monkeypatch.setattr(
        db_connection.Base.metadata,
        "create_all",
        lambda **kwargs: None,
    )

    import app.main as main_module

    try:
        reloaded_module = importlib.reload(main_module)

        assert reloaded_module.app.state.db_ready is False
        assert reloaded_module.app.state.db_error == "Database unavailable"
    finally:
        importlib.reload(main_module)

