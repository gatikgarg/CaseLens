from evaluation.metrics import collapse, mrr, ndcg_at_k, precision_at_k, recall_at_k


def test_collapse_dedupes_in_rank_order():
    assert collapse(["a", "b", "a", "c"]) == ["a", "b", "c"]


def test_recall_precision():
    assert recall_at_k(["a", "b", "c"], {"a", "x"}, 2) == 0.5
    assert precision_at_k(["a", "b"], {"a"}, 2) == 0.5


def test_mrr_and_ndcg():
    assert mrr(["x", "a"], {"a"}) == 0.5
    assert ndcg_at_k(["a", "b"], {"a"}, 10) == 1.0
    assert ndcg_at_k([], {"a"}, 10) == 0.0

