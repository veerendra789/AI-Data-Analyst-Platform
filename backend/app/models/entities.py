from __future__ import annotations

from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


class DatasetStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MessageRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(String(20), default=UserRole.ANALYST, nullable=False)

    datasets: Mapped[list[Dataset]] = relationship(back_populates="user", cascade="all, delete-orphan")
    queries: Mapped[list[Query]] = relationship(back_populates="user", cascade="all, delete-orphan")
    chat_messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    reports: Mapped[list[Report]] = relationship(back_populates="user", cascade="all, delete-orphan")
    visualizations: Mapped[list[Visualization]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Dataset(TimestampMixin, Base):
    __tablename__ = "datasets"
    __table_args__ = (
        Index("ix_datasets_user_id_created_at", "user_id", "created_at"),
        Index("ix_datasets_source_preparation_id_unique", "source_preparation_id", unique=True),
        CheckConstraint("row_count >= 0", name="ck_datasets_row_count_nonnegative"),
        CheckConstraint("column_count >= 0", name="ck_datasets_column_count_nonnegative"),
        CheckConstraint("file_size >= 0", name="ck_datasets_file_size_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[DatasetStatus] = mapped_column(String(20), nullable=False, default=DatasetStatus.PENDING)
    source_preparation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    user: Mapped[User] = relationship(back_populates="datasets")
    columns: Mapped[list[DatasetColumn]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
    queries: Mapped[list[Query]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
    chat_messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
    analysis_results: Mapped[list[AnalysisResult]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
    reports: Mapped[list[Report]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
    visualizations: Mapped[list[Visualization]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class DatasetColumn(Base):
    __tablename__ = "dataset_columns"
    __table_args__ = (
        Index("ix_dataset_columns_dataset_id", "dataset_id"),
        Index("ix_dataset_columns_dataset_id_column_name", "dataset_id", "column_name", unique=True),
        CheckConstraint("unique_count >= 0", name="ck_dataset_columns_unique_count_nonnegative"),
        CheckConstraint("missing_count >= 0", name="ck_dataset_columns_missing_count_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(String(100), nullable=False)
    nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    unique_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    dataset: Mapped[Dataset] = relationship(back_populates="columns")


class DataPreparationSession(TimestampMixin, Base):
    __tablename__ = "data_preparation_sessions"
    __table_args__ = (Index("ix_data_preparation_sessions_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    output_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ANALYZED")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    plan_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    history_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)


class Query(TimestampMixin, Base):
    __tablename__ = "queries"
    __table_args__ = (
        Index("ix_queries_user_id_created_at", "user_id", "created_at"),
        Index("ix_queries_dataset_id_created_at", "dataset_id", "created_at"),
        CheckConstraint("execution_time >= 0", name="ck_queries_execution_time_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    generated_sql: Mapped[str | None] = mapped_column(Text)
    execution_time: Mapped[float | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")

    user: Mapped[User] = relationship(back_populates="queries")
    dataset: Mapped[Dataset] = relationship(back_populates="queries")
    visualizations: Mapped[list[Visualization]] = relationship(back_populates="query")


class ChatMessage(TimestampMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_dataset_id_created_at", "dataset_id", "created_at"),
        Index("ix_chat_messages_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[MessageRole] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    user: Mapped[User] = relationship(back_populates="chat_messages")
    dataset: Mapped[Dataset] = relationship(back_populates="chat_messages")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (Index("ix_analysis_results_dataset_id_created_at", "dataset_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    query_id: Mapped[int | None] = mapped_column(ForeignKey("queries.id", ondelete="CASCADE"))
    analysis_type: Mapped[str] = mapped_column(String(50), nullable=False)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    dataset: Mapped[Dataset] = relationship(back_populates="analysis_results")
    query: Mapped[Query | None] = relationship()


class Report(TimestampMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (Index("ix_reports_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    user: Mapped[User] = relationship(back_populates="reports")
    dataset: Mapped[Dataset] = relationship(back_populates="reports")


class Visualization(TimestampMixin, Base):
    __tablename__ = "visualizations"
    __table_args__ = (Index("ix_visualizations_dataset_id_created_at", "dataset_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    query_id: Mapped[int | None] = mapped_column(ForeignKey("queries.id", ondelete="SET NULL"))
    chart_type: Mapped[str] = mapped_column(String(30), nullable=False)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    user: Mapped[User] = relationship(back_populates="visualizations")
    dataset: Mapped[Dataset] = relationship(back_populates="visualizations")
    query: Mapped[Query | None] = relationship(back_populates="visualizations")
