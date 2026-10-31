from backend.app.retrieval.filters import Filters


def test_defaults_are_empty():
    f = Filters()
    assert f.priority is None
    assert f.created_from is None


def test_to_qdrant_builds_filter():
    pytest = __import__("pytest")
    pytest.importorskip("qdrant_client")
    flt = Filters(priority=["High"], has_conversation=True).to_qdrant()
    assert flt is not None

