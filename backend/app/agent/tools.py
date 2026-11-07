from app.rag.retriever import retrieve_relevant_chunks
from sqlalchemy import func
from app.database.connection import SessionLocal
from app.database.models import (
    Document,
    Conversation,
    ConversationMessage
)



def search_document_content(question: str, user_id: int):
    if not isinstance(question, str):
        raise ValueError("Question must be a string.")

    question = question.strip()

    if not question:
        raise ValueError("Question cannot be empty.")

    if len(question) > 1000:
        raise ValueError("Question is too long.")

    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("Invalid user ID.")

    results = retrieve_relevant_chunks(
        question,
        user_id=user_id,
        limit=3
    )

    return [
        {
            "document_id": result.document_id,
            "chunk": result.chunk_text
        }
        for result in results
    ]
def query_business_data(action: str, user_id: int):
    if not isinstance(action, str):
        raise ValueError("Action must be a string.")

    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("Invalid user ID.")

    allowed_actions = {
        "document_count",
        "document_list",
        "conversation_count",
        "recent_conversations",
        "message_count",
    }

    if action not in allowed_actions:
        raise ValueError("Unsupported business data action.")

    db = SessionLocal()

    try:
        if action == "document_count":
            count = db.query(func.count(Document.id)).filter(
                Document.user_id == user_id
            ).scalar()

            return {"document_count": count or 0}

        elif action == "document_list":
            documents = db.query(Document).filter(
                Document.user_id == user_id
            ).order_by(Document.uploaded_at.desc()).limit(10).all()

            return {
                "documents": [
                    {
                        "id": doc.id,
                        "filename": doc.filename,
                        "uploaded_at": (
                            doc.uploaded_at.isoformat()
                            if doc.uploaded_at else None
                        ),
                    }
                    for doc in documents
                ]
            }

        elif action == "conversation_count":
            count = db.query(func.count(Conversation.id)).filter(
                Conversation.user_id == user_id
            ).scalar()

            return {"conversation_count": count or 0}

        elif action == "recent_conversations":
            conversations = db.query(Conversation).filter(
                Conversation.user_id == user_id
            ).order_by(
                Conversation.created_at.desc()
            ).limit(5).all()

            return {
                "conversations": [
                    {
                        "conversation_id": conv.conversation_id,
                        "created_at": (
                            conv.created_at.isoformat()
                            if conv.created_at else None
                        ),
                    }
                    for conv in conversations
                ]
            }

        else:
            count = (
                db.query(func.count(ConversationMessage.id))
                .join(
                    Conversation,
                    Conversation.conversation_id
                    == ConversationMessage.conversation_id
                )
                .filter(Conversation.user_id == user_id)
                .scalar()
            )

            return {"message_count": count or 0}

    finally:
        db.close()