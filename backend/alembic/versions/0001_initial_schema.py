"""Create the initial application schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("column_count", sa.Integer(), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("row_count >= 0", name="ck_datasets_row_count_nonnegative"),
        sa.CheckConstraint("column_count >= 0", name="ck_datasets_column_count_nonnegative"),
        sa.CheckConstraint("file_size >= 0", name="ck_datasets_file_size_nonnegative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_datasets_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_datasets"),
    )
    op.create_index("ix_datasets_user_id_created_at", "datasets", ["user_id", "created_at"])

    op.create_table(
        "dataset_columns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("column_name", sa.String(length=255), nullable=False),
        sa.Column("data_type", sa.String(length=100), nullable=False),
        sa.Column("nullable", sa.Boolean(), nullable=False),
        sa.Column("unique_count", sa.Integer(), nullable=False),
        sa.Column("missing_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("unique_count >= 0", name="ck_dataset_columns_unique_count_nonnegative"),
        sa.CheckConstraint("missing_count >= 0", name="ck_dataset_columns_missing_count_nonnegative"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], name="fk_dataset_columns_dataset_id_datasets", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_dataset_columns"),
        sa.UniqueConstraint("dataset_id", "column_name", name="uq_dataset_columns_dataset_id"),
    )
    op.create_index("ix_dataset_columns_dataset_id", "dataset_columns", ["dataset_id"])

    op.create_table(
        "queries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("generated_sql", sa.Text(), nullable=True),
        sa.Column("execution_time", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("execution_time >= 0", name="ck_queries_execution_time_nonnegative"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], name="fk_queries_dataset_id_datasets", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_queries_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_queries"),
    )
    op.create_index("ix_queries_user_id_created_at", "queries", ["user_id", "created_at"])
    op.create_index("ix_queries_dataset_id_created_at", "queries", ["dataset_id", "created_at"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], name="fk_chat_messages_dataset_id_datasets", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_chat_messages_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_chat_messages"),
    )
    op.create_index("ix_chat_messages_dataset_id_created_at", "chat_messages", ["dataset_id", "created_at"])
    op.create_index("ix_chat_messages_user_id_created_at", "chat_messages", ["user_id", "created_at"])

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("analysis_type", sa.String(length=50), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], name="fk_analysis_results_dataset_id_datasets", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_analysis_results"),
    )
    op.create_index("ix_analysis_results_dataset_id_created_at", "analysis_results", ["dataset_id", "created_at"])

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], name="fk_reports_dataset_id_datasets", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_reports_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_reports"),
    )
    op.create_index("ix_reports_user_id_created_at", "reports", ["user_id", "created_at"])

    op.create_table(
        "visualizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("query_id", sa.Integer(), nullable=True),
        sa.Column("chart_type", sa.String(length=30), nullable=False),
        sa.Column("configuration_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], name="fk_visualizations_dataset_id_datasets", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["query_id"], ["queries.id"], name="fk_visualizations_query_id_queries", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_visualizations_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_visualizations"),
    )
    op.create_index("ix_visualizations_dataset_id_created_at", "visualizations", ["dataset_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_visualizations_dataset_id_created_at", table_name="visualizations")
    op.drop_table("visualizations")
    op.drop_index("ix_reports_user_id_created_at", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_analysis_results_dataset_id_created_at", table_name="analysis_results")
    op.drop_table("analysis_results")
    op.drop_index("ix_chat_messages_user_id_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_dataset_id_created_at", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_queries_dataset_id_created_at", table_name="queries")
    op.drop_index("ix_queries_user_id_created_at", table_name="queries")
    op.drop_table("queries")
    op.drop_index("ix_dataset_columns_dataset_id", table_name="dataset_columns")
    op.drop_table("dataset_columns")
    op.drop_index("ix_datasets_user_id_created_at", table_name="datasets")
    op.drop_table("datasets")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
