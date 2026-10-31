import pytest

from backend.app.analytics.query_builder import AnalyticsArgs, AnalyticsError, run_analytics


def test_unknown_metric_raises_with_valid_names():
    with pytest.raises(AnalyticsError, match="valid:"):
        run_analytics(AnalyticsArgs(metric="nope"), "D1")


def test_unknown_dimension_raises():
    with pytest.raises(AnalyticsError, match="unknown dimension"):
        run_analytics(AnalyticsArgs(metric="ticket_count", dimension="nope"), "D1")


def test_sql_guard_rejects_injection():
    sqlglot = pytest.importorskip("sqlglot")
    from backend.app.analytics.sql_guard import guard

    ok, msg = guard("SELECT * FROM ticket_facts; DROP TABLE tickets;")
    assert not ok
    assert "multiple statements" in msg

