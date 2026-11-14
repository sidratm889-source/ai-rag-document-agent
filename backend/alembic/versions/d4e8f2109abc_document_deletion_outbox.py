"""Add document deletion outbox.

Revision ID: d4e8f2109abc
Revises: f5ce0f5b4039
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d4e8f2109abc"
down_revision: Union[str, Sequence[str], None] = "f5ce0f5b4039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "document_deletion_outbox",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_token", sa.String(length=36), nullable=True),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="ck_document_deletion_outbox_attempts_nonnegative",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_document_deletion_outbox_status",
        ),
        sa.CheckConstraint(
            "(status = 'processing' AND lease_until IS NOT NULL "
            "AND lease_token IS NOT NULL) OR "
            "(status <> 'processing' AND lease_until IS NULL "
            "AND lease_token IS NULL)",
            name="ck_document_deletion_outbox_lease_state",
        ),
        sa.CheckConstraint(
            "(status = 'completed') = (completed_at IS NOT NULL)",
            name="ck_document_deletion_outbox_completion_state",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_deletion_outbox"),
        sa.UniqueConstraint("document_id", name="uq_document_deletion_outbox_document_id"),
        sa.UniqueConstraint("lease_token", name="uq_document_deletion_outbox_lease_token"),
    )
    op.create_index(
        "ix_document_deletion_outbox_pending_available_at",
        "document_deletion_outbox",
        ["available_at", "id"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_document_deletion_outbox_processing_lease_until",
        "document_deletion_outbox",
        ["lease_until", "id"],
        unique=False,
        postgresql_where=sa.text("status = 'processing'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_document_deletion_outbox_processing_lease_until",
        table_name="document_deletion_outbox",
    )
    op.drop_index(
        "ix_document_deletion_outbox_pending_available_at",
        table_name="document_deletion_outbox",
    )
    op.drop_table("document_deletion_outbox")
