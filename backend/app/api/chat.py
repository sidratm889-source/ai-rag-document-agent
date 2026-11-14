import logging

from fastapi import APIRouter, Depends, HTTPException
from ollama import ResponseError
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.database.models import Conversation, ConversationMessage, User
from app.agent.agent import (
    _asks_about_previous_message,
    create_conversation,
    is_business_data_question,
    run_agent,
    run_source_only_document_query,
)
from app.agent.tools import answer_document_question

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=1000
    )
    conversation_id: str | None = Field(
        default=None,
        description=(
            "Existing conversation ID. Omit this field to start a new conversation."
        ),
    )
    document_id: int | None = Field(default=None, gt=0)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question cannot be empty.")
        return cleaned

    @field_validator("conversation_id")
    @classmethod
    def normalize_conversation_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
            
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Conversation ID cannot be empty.")
        return cleaned


class AgentChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = Field(
        default=None,
        description=(
            "Existing conversation ID. Omit this field to start a new conversation."
        ),
    )
    document_id: int | None = Field(default=None, gt=0)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question cannot be empty.")
        return cleaned

    @field_validator("conversation_id")
    @classmethod
    def normalize_conversation_id(cls, value: str | None) -> str | None:
        if value is None:
            return None

        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Conversation ID cannot be empty.")
        return cleaned

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "question": "Summarize the uploaded documents.",
                    "conversation_id": "existing-conversation-id",
                }
            ]
        }
    }


class ChatResponse(BaseModel):
    question: str
    answer: str
    conversation_id: str


@router.post("/", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        if request.conversation_id is None:
            conversation_id = create_conversation(current_user.id)
        else:
            conversation = db.query(Conversation).filter(
                Conversation.conversation_id == request.conversation_id,
                Conversation.user_id == current_user.id,
            ).first()

            if conversation is None:
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found.",
                )

            conversation_id = conversation.conversation_id
    except SQLAlchemyError as error:
        logger.exception("Database error while accessing chat conversation")
        raise HTTPException(
            status_code=503,
            detail="Conversation service is temporarily unavailable.",
        ) from error

    answer_options = {"user_id": current_user.id}
    if request.document_id is not None:
        answer_options["document_id"] = request.document_id
    answer = answer_document_question(request.question, **answer_options)

    try:
        db.add_all([
            ConversationMessage(
                conversation_id=conversation_id,
                role="user",
                content=request.question,
            ),
            ConversationMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=answer,
            ),
        ])
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Database error while saving chat messages")
        raise HTTPException(
            status_code=503,
            detail="Conversation service is temporarily unavailable.",
        ) from error

    return {
        "question": request.question,
        "answer": answer,
        "conversation_id": conversation_id,
    }
    
@router.post("/agent", response_model=ChatResponse)
def agent_chat(
    request: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        if request.conversation_id is None:
            conversation_id = create_conversation(current_user.id)
        else:
            conversation = db.query(Conversation).filter(
                Conversation.conversation_id == request.conversation_id,
                Conversation.user_id == current_user.id,
            ).first()

            if conversation is None:
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found.",
                )

            conversation_id = conversation.conversation_id
    except SQLAlchemyError as error:
        logger.exception("Database error while accessing chat conversation")
        raise HTTPException(
            status_code=503,
            detail="Conversation service is temporarily unavailable.",
        ) from error

    if (
        _asks_about_previous_message(request.question)
        or is_business_data_question(request.question)
    ):
        try:
            answer = run_agent(
                question=request.question,
                conversation_id=conversation_id,
                user_id=current_user.id,
            )
        except ResponseError as error:
            if "unable to allocate cpu buffer" not in error.error.casefold():
                raise

            raise HTTPException(
                status_code=503,
                detail=(
                    "Ollama could not load the configured model because the system "
                    "does not have enough available memory. Free memory or configure "
                    "a smaller model, then pull it with Ollama."
                ),
            ) from error
    else:
        source_query_options = {
            "question": request.question,
            "conversation_id": conversation_id,
            "user_id": current_user.id,
        }
        if request.document_id is not None:
            source_query_options["document_id"] = request.document_id
        answer = run_source_only_document_query(**source_query_options)

    return {
        "question":request.question,
        "answer": answer,
        "conversation_id":conversation_id,
    }
