"""Optional guarded text-to-SQL fallback. Disabled by default.

The semantic layer is the primary path. If enabled, every statement must pass
these checks before it is executed against the read-only role.
"""
import logging

log = logging.getLogger(__name__)

ALLOWED_TABLES = {"ticket_facts", "dataset_coverage"}
BLOCKED = {"pg_", "information_schema"}


def guard(sql: str) -> tuple[bool, str]:
    import sqlglot

    if ";" in sql:
        return False, "multiple statements are not allowed"
    lower = sql.lower()
    if any(b in lower for b in BLOCKED):
        return False, "system catalogs are not allowed"
    try:
        parsed = sqlglot.parse_one(sql)
    except Exception as e:
        return False, f"parse error: {e}"
    if parsed.key != "select":
        return False, "only a single SELECT is allowed"
    tables = {t.name.lower() for t in parsed.find_all(sqlglot.exp.Table)}
    if not tables.issubset(ALLOWED_TABLES):
        return False, f"tables not allowed: {tables - ALLOWED_TABLES}"
    if parsed.find(sqlglot.exp.Limit) is None:
        sql = sql.rstrip().rstrip(";") + " LIMIT 100"
    return True, sql

