
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv

from sqlalchemy import pool

load_dotenv()

# Import all models so SQLAlchemy registers their tables.
from app.database import models
from app.database.connection import Base, engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Make all SQLAlchemy models available to Alembic.
target_metadata = Base.metadata
def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name == "documents" and reflected:
        return False

    return True

def run_migrations_offline() -> None:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")

    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
    
else:
    run_migrations_online()
