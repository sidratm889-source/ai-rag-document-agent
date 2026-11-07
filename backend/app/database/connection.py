import os
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from unittest.mock import MagicMock

from app.database import connection as db_connection


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass

def create_user_table():
    from app.database.models import User

    Base.metadata.create_all(
        bind=engine,
        tables=[User.__table__]
    )


def ensure_pgvector_extension():
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def ensure_conversation_schema():
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS conversations ("
                "id SERIAL PRIMARY KEY, "
                "conversation_id VARCHAR NOT NULL UNIQUE, "
                "user_id INTEGER, "
                "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE conversations "
                "ADD COLUMN IF NOT EXISTS id SERIAL"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE conversations "
                "ADD COLUMN IF NOT EXISTS conversation_id VARCHAR"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE conversations "
                "ADD COLUMN IF NOT EXISTS user_id INTEGER"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE conversations "
                "ADD COLUMN IF NOT EXISTS created_at TIMESTAMP "
                "DEFAULT CURRENT_TIMESTAMP"
            )
        )

        rows_without_conversation_id = connection.execute(
            text("SELECT ctid::text FROM conversations WHERE conversation_id IS NULL")
        ).scalars().all()
        for row_ctid in rows_without_conversation_id:
            connection.execute(
                text(
                    "UPDATE conversations SET conversation_id = :conversation_id "
                    "WHERE ctid = CAST(:row_ctid AS tid)"
                ),
                {"conversation_id": str(uuid4()), "row_ctid": row_ctid},
            )

        connection.execute(
            text(
                "UPDATE conversations SET created_at = CURRENT_TIMESTAMP "
                "WHERE created_at IS NULL"
            )
        )
        connection.execute(
            text("ALTER TABLE conversations ALTER COLUMN id SET NOT NULL")
        )
        connection.execute(
            text(
                "ALTER TABLE conversations "
                "ALTER COLUMN conversation_id SET NOT NULL"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE conversations "
                "ALTER COLUMN created_at SET NOT NULL"
            )
        )
        connection.execute(
            text(
                "DO $$ BEGIN "
                "IF NOT EXISTS ("
                "SELECT 1 FROM pg_constraint "
                "WHERE conrelid = 'conversations'::regclass AND contype = 'p'"
                ") THEN "
                "ALTER TABLE conversations "
                "ADD CONSTRAINT conversations_pkey PRIMARY KEY (id); "
                "END IF; "
                "END $$"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "conversations_conversation_id_key "
                "ON conversations (conversation_id)"
            )
        )

def ensure_conversation_messages_schema():
    from app.database.models import ConversationMessage

    Base.metadata.create_all(
        bind=engine,
        tables=[ConversationMessage.__table__]
    )

