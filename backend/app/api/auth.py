
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from fastapi import Depends
from app.database.connection import SessionLocal
from app.database.models import User
from fastapi.security import OAuth2PasswordRequestForm
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    email = str(data.email).lower()

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email is already registered.",
        )

    user = User(
        email=email,
        hashed_password=hash_password(data.password),
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not create user.",
        )

    return {"id": user.id, "email": user.email}


@router.post("/login", response_model=TokenResponse)
def login_user(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    email = str(data.email).lower()
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user.id)

    return {
        "access_token": token,
        "token_type": "bearer",
    }

@router.post("/token", response_model=TokenResponse)
def swagger_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    email = form_data.username.lower().strip()

    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(
        form_data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = create_access_token(user.id)

    return {
        "access_token": token,
        "token_type": "bearer"
    }

@router.get("/me")
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "email": current_user.email,
    }
