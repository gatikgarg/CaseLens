"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("run_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_file", sa.String(), nullable=False),
        sa.Column("file_sha256", sa.String(), nullable=False),
        sa.Column("target_table", sa.String(), nullable=False),
        sa.Column("rows_read", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_loaded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates_removed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_ingestion_runs_file_sha256", "ingestion_runs", ["file_sha256"])

    op.create_table(
        "ingestion_rejects",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("row_json", JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["ingestion_runs.run_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_rejects_run_id", "ingestion_rejects", ["run_id"])

    op.create_table(
        "tickets",
        sa.Column("ticket_id", sa.String(), nullable=False),
        sa.Column("source_system", sa.String(), nullable=False, server_default="mendeley_helpdesk_v3"),
        sa.Column("project_id", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("priority", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw", JSONB(), nullable=False),
        sa.Column("row_hash", sa.String(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["ingestion_runs.run_id"]),
        sa.PrimaryKeyConstraint("ticket_id"),
    )
    op.create_index("ix_tickets_project_id", "tickets", ["project_id"])
    op.create_index("ix_tickets_category", "tickets", ["category"])
    op.create_index("ix_tickets_priority", "tickets", ["priority"])
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_created_at", "tickets", ["created_at"])

    op.create_table(
        "ticket_events",
        sa.Column("event_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.String(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("field", sa.String(), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("raw", JSONB(), nullable=False),
        sa.Column("row_hash", sa.String(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["ingestion_runs.run_id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"]),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("row_hash"),
    )
    op.create_index("ix_ticket_events_ticket_id", "ticket_events", ["ticket_id"])
    op.create_index("ix_ticket_events_field", "ticket_events", ["field"])

    op.create_table(
        "utterances",
        sa.Column("utterance_id", sa.String(), nullable=False),
        sa.Column("ticket_id", sa.String(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("speaker_role", sa.String(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw", JSONB(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["ingestion_runs.run_id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"]),
        sa.PrimaryKeyConstraint("utterance_id"),
    )
    op.create_index("ix_utterances_ticket_id", "utterances", ["ticket_id"])

    op.create_table(
        "holidays",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("country", sa.String(), nullable=False),
        sa.Column("day", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("raw", JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_holidays_country", "holidays", ["country"])

    op.create_table(
        "ticket_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.String(), nullable=True),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw", JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_snapshots_ticket_id", "ticket_snapshots", ["ticket_id"])

    op.create_table(
        "documents",
        sa.Column("doc_id", sa.String(), nullable=False),
        sa.Column("parent_id", sa.String(), nullable=True),
        sa.Column("ticket_id", sa.String(), nullable=False),
        sa.Column("doc_type", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("indexed_hash", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("doc_id"),
    )
    op.create_index("ix_documents_parent_id", "documents", ["parent_id"])
    op.create_index("ix_documents_ticket_id", "documents", ["ticket_id"])
    op.create_index("ix_documents_doc_type", "documents", ["doc_type"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("response_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])


def downgrade() -> None:
    for table in [
        "messages",
        "conversations",
        "documents",
        "ticket_snapshots",
        "holidays",
        "utterances",
        "ticket_events",
        "tickets",
        "ingestion_rejects",
        "ingestion_runs",
    ]:
        op.drop_table(table)

