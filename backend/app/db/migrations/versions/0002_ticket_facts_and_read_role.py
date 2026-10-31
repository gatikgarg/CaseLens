"""ticket facts and read-only role

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-31
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE MATERIALIZED VIEW ticket_facts AS
        SELECT
          t.ticket_id, t.project_id, t.category, t.priority, t.status, t.country,
          t.created_at, t.resolved_at,
          CASE WHEN t.resolved_at >= t.created_at
               THEN EXTRACT(EPOCH FROM (t.resolved_at - t.created_at))/3600.0 END AS resolution_hours,
          (t.resolved_at IS NOT NULL) AS is_resolved,
          COALESCE(e.n_events, 0)      AS n_events,
          COALESCE(e.n_reassign, 0)    AS n_reassignments,
          EXISTS (SELECT 1 FROM utterances u WHERE u.ticket_id = t.ticket_id) AS has_conversation
        FROM tickets t
        LEFT JOIN (
          SELECT ticket_id, COUNT(*) AS n_events,
                 COUNT(*) FILTER (WHERE field ILIKE '%assign%') AS n_reassign
          FROM ticket_events GROUP BY ticket_id
        ) e USING (ticket_id);
        """
    )
    op.execute("CREATE UNIQUE INDEX ON ticket_facts (ticket_id);")
    op.execute("CREATE INDEX ON ticket_facts (created_at);")
    op.execute("CREATE INDEX ON ticket_facts (category);")
    op.execute("CREATE INDEX ON ticket_facts (priority);")

    op.execute(
        """
        CREATE VIEW dataset_coverage AS
        SELECT COUNT(*) AS total_tickets,
               COUNT(*) FILTER (WHERE has_conversation) AS tickets_with_conversation,
               COUNT(*) FILTER (WHERE resolution_hours IS NOT NULL) AS tickets_with_resolution_time,
               MIN(created_at) AS first_ticket_at, MAX(created_at) AS last_ticket_at
        FROM ticket_facts;
        """
    )
    op.execute("CREATE ROLE sl_readonly LOGIN PASSWORD 'sl_readonly';")
    op.execute("GRANT CONNECT ON DATABASE supportlens TO sl_readonly;")
    op.execute("GRANT USAGE ON SCHEMA public TO sl_readonly;")
    op.execute("GRANT SELECT ON ticket_facts, dataset_coverage TO sl_readonly;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS dataset_coverage;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ticket_facts;")
    op.execute("DROP ROLE IF EXISTS sl_readonly;")

