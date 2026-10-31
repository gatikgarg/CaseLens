from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_file: Mapped[str] = mapped_column(String)
    file_sha256: Mapped[str] = mapped_column(String, index=True)
    target_table: Mapped[str] = mapped_column(String)
    rows_read: Mapped[int] = mapped_column(Integer, default=0)
    rows_loaded: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_removed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IngestionReject(Base):
    __tablename__ = "ingestion_rejects"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.run_id"), index=True)
    reason: Mapped[str] = mapped_column(String)
    row_json: Mapped[dict] = mapped_column(JSONB)


class Ticket(Base):
    __tablename__ = "tickets"
    ticket_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_system: Mapped[str] = mapped_column(String, default="mendeley_helpdesk_v3")
    project_id: Mapped[str | None] = mapped_column(String, index=True)
    category: Mapped[str | None] = mapped_column(String, index=True)
    priority: Mapped[str | None] = mapped_column(String, index=True)
    status: Mapped[str | None] = mapped_column(String, index=True)
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw: Mapped[dict] = mapped_column(JSONB)
    row_hash: Mapped[str] = mapped_column(String)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.run_id"))


class TicketEvent(Base):
    __tablename__ = "ticket_events"
    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.ticket_id"), index=True)
    changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    field: Mapped[str | None] = mapped_column(String, index=True)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict] = mapped_column(JSONB)
    row_hash: Mapped[str] = mapped_column(String, unique=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.run_id"))


class Utterance(Base):
    __tablename__ = "utterances"
    utterance_id: Mapped[str] = mapped_column(String, primary_key=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.ticket_id"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    speaker_role: Mapped[str | None] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw: Mapped[dict] = mapped_column(JSONB)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.run_id"))


class Holiday(Base):
    __tablename__ = "holidays"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    country: Mapped[str] = mapped_column(String, index=True)
    day: Mapped[datetime] = mapped_column(DateTime)
    name: Mapped[str | None] = mapped_column(String)
    raw: Mapped[dict] = mapped_column(JSONB)


class TicketSnapshot(Base):
    __tablename__ = "ticket_snapshots"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str | None] = mapped_column(String, index=True)
    snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw: Mapped[dict] = mapped_column(JSONB)


class Document(Base):
    __tablename__ = "documents"
    doc_id: Mapped[str] = mapped_column(String, primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(String, index=True)
    ticket_id: Mapped[str] = mapped_column(String, index=True)
    doc_type: Mapped[str] = mapped_column(String, index=True)
    text: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String)
    indexed_hash: Mapped[str | None] = mapped_column(String)


class ConversationRow(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MessageRow(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    response_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


Index("ix_tickets_created_at", Ticket.created_at)
Index("ix_documents_parent_id", Document.parent_id)

