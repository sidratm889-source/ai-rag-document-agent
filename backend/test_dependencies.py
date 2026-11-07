
from types import SimpleNamespace
from time import time
from unittest.mock import MagicMock

import pytest
import jwt
from fastapi import HTTPException

from app.api import dependencies


def test_missing_jwt_secret_key(monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    with pytest.raises(HTTPException) as exc:
        dependencies.get_current_user(
            token="some-token",
            db=MagicMock(),
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "Authentication is not configured."


def test_invalid_token(monkeypatch):
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "test-secret-key-for-unit-tests-32-bytes-min"
    )

    with pytest.raises(HTTPException) as exc:
        dependencies.get_current_user(
            token="invalid-token",
            db=MagicMock(),
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid or expired token."
    assert exc.value.headers["WWW-Authenticate"] == "Bearer"


def test_invalid_token_subject(monkeypatch):
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "test-secret-key-for-unit-tests-32-bytes-min"
    )

    token = jwt.encode(
        {"sub": "not-a-number", "exp": int(time()) + 60},
        "test-secret-key-for-unit-tests-32-bytes-min",
        algorithm=dependencies.ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc:
        dependencies.get_current_user(token=token, db=MagicMock())

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid or expired token."


@pytest.mark.parametrize(
    "payload",
    [
        {"sub": "5"},
        {"exp": int(time()) + 60},
    ],
)
def test_token_missing_required_claim_is_rejected(monkeypatch, payload):
    secret_key = "test-secret-key-for-unit-tests-32-bytes-min"
    monkeypatch.setenv("JWT_SECRET_KEY", secret_key)
    token = jwt.encode(
        payload,
        secret_key,
        algorithm=dependencies.ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc:
        dependencies.get_current_user(token=token, db=MagicMock())

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid or expired token."


def test_user_not_found(monkeypatch):
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "test-secret-key-for-unit-tests-32-bytes-min"
    )

    token = jwt.encode(
        {"sub": "999999", "exp": int(time()) + 60},
        "test-secret-key-for-unit-tests-32-bytes-min",
        algorithm=dependencies.ALGORITHM,
    )

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc:
        dependencies.get_current_user(token=token, db=db)

    assert exc.value.status_code == 401
    assert exc.value.detail == "User not found."
    assert exc.value.headers["WWW-Authenticate"] == "Bearer"


def test_valid_token_returns_user(monkeypatch):
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "test-secret-key-for-unit-tests-32-bytes-min"
    )

    token = jwt.encode(
        {"sub": "5", "exp": int(time()) + 60},
        "test-secret-key-for-unit-tests-32-bytes-min",
        algorithm=dependencies.ALGORITHM,
    )

    expected_user = SimpleNamespace(id=5, email="test@example.com")

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = expected_user

    result = dependencies.get_current_user(token=token, db=db)

    assert result is expected_user
    db.query.assert_called_once_with(dependencies.User)
    
def test_get_db_yields_session_and_closes_it(monkeypatch):
    mock_db = MagicMock()
    monkeypatch.setattr(
        dependencies, "SessionLocal", lambda: mock_db
    )

    db_generator = dependencies.get_db()

    assert next(db_generator) is mock_db

    with pytest.raises(StopIteration):
        next(db_generator)

    mock_db.close.assert_called_once()


def test_get_db_closes_session_when_generator_closes(monkeypatch):
    mock_db = MagicMock()
    monkeypatch.setattr(
        dependencies, "SessionLocal", lambda: mock_db
    )

    db_generator = dependencies.get_db()

    assert next(db_generator) is mock_db

    db_generator.close()

    mock_db.close.assert_called_once()
