"""Persist data preparation sessions and dataset lineage.

Revision ID: 0003_data_preparation
Revises: 0002_analysis_result_query
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_data_preparation"
down_revision: Union[str, None] = "0002_analysis_result_query"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("source_preparation_id", sa.String(length=36), nullable=True))
    op.create_index("ix_datasets_source_preparation_id_unique", "datasets", ["source_preparation_id"], unique=True)
    op.create_table(
        "data_preparation_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("source_path", sa.String(length=1024), nullable=False),
        sa.Column("output_path", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("history_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_preparation_sessions_user_id_created_at", "data_preparation_sessions", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_data_preparation_sessions_user_id_created_at", table_name="data_preparation_sessions")
    op.drop_table("data_preparation_sessions")
    op.drop_index("ix_datasets_source_preparation_id_unique", table_name="datasets")
    op.drop_column("datasets", "source_preparation_id")