"""Add source metadata to document chunks."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c36a7b9d1e24"
down_revision: Union[str, Sequence[str], None] = "d4e8f2109abc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column("page_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("section_heading", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "section_heading")
    op.drop_column("document_chunks", "page_number")
