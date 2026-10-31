from types import SimpleNamespace

from backend.app.retrieval.fusion import rrf


def _hit(i):
    return SimpleNamespace(id=i, scores={}, ranks={})


def test_rrf_hand_computed_order():
    a = [_hit("a"), _hit("b"), _hit("c")]
    b = [_hit("b"), _hit("c"), _hit("d")]
    out = rrf([a, b], k=60)
    assert [h.id for h in out] == ["b", "c", "a", "d"]
    assert abs(out[0].scores["rrf"] - (1 / 61 + 1 / 62)) < 1e-9


def test_rrf_merges_scores_and_ranks():
    a = [_hit("x")]
    b = [_hit("x")]
    out = rrf([a, b], k=60)
    assert out[0].ranks["rrf"] == 1

