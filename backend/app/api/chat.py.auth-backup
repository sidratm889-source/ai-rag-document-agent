import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.rag.retriever import retrieve_relevant_chunks
from app.services.llm import generate_answer
from app.api.dependencies import get_current_user, get_db
from app.database.models import Conversation, ConversationMessage, User
from app.agent.agent import run_agent, create_conversation

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

    results = retrieve_relevant_chunks(
        request.question,
        user_id=current_user.id
    )

    if not results:
        answer = (
            "I couldn't find relevant information "
            "in the uploaded documents."
        )
    else:
        context = "\n\n".join(
            chunk.chunk_text for chunk in results
        )
        answer = generate_answer(request.question, context)

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

    answer = run_agent(
        question=request.question,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    return {
        "question":request.question,
        "answer": answer,
        "conversation_id":conversation_id,
    }
