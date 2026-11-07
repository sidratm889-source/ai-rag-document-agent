import jwt
import pytest

from app.services import auth_service


def test_hash_password_does_not_return_plain_password():
    password = "StrongPassword123!"
    hashed = auth_service.hash_password(password)

    assert hashed != password
    assert auth_service.verify_password(password, hashed)


def test_verify_password_rejects_wrong_password():
    hashed = auth_service.hash_password("CorrectPassword123!")

    assert not auth_service.verify_password("WrongPassword123!", hashed)


def test_create_access_token_contains_user_id_and_expiry(monkeypatch):
    test_secret = "test-secret-key-at-least-32-bytes-long"
    monkeypatch.setattr(auth_service, "SECRET_KEY", test_secret)

    token = auth_service.create_access_token(123)

    payload = jwt.decode(
        token,
        test_secret,
        algorithms=[auth_service.ALGORITHM],
    )

    assert payload["sub"] == "123"
    assert "exp" in payload


def test_create_access_token_fails_without_secret_key(monkeypatch):
    monkeypatch.setattr(auth_service, "SECRET_KEY", None)

    with pytest.raises(
        RuntimeError,
        match="JWT_SECRET_KEY is not configured",
    ):
        auth_service.create_access_token(123)
