
import os

import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import User
from app.services.auth_service import ALGORITHM


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    secret_key = os.getenv("JWT_SECRET_KEY")

    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication is not configured.",
        )

    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        user_id = payload.get("sub")

        if not isinstance(user_id, str) or not user_id.isdigit():
            raise InvalidTokenError("Invalid subject")

    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == int(user_id)).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
