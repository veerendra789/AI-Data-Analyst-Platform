"""Associate persisted analysis results with queries.

Revision ID: 0002_analysis_result_query
Revises: 0001_initial_schema
Create Date: 2026-09-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_analysis_result_query"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("analysis_results") as batch_op:
        batch_op.add_column(sa.Column("query_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_analysis_results_query_id_queries",
            "queries",
            ["query_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_analysis_results_query_id", ["query_id"])


def downgrade() -> None:
    with op.batch_alter_table("analysis_results") as batch_op:
        batch_op.drop_index("ix_analysis_results_query_id")
        batch_op.drop_constraint("fk_analysis_results_query_id_queries", type_="foreignkey")
        batch_op.drop_column("query_id")