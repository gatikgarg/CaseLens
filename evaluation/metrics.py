import math
import random
import statistics


def collapse(ranked_ticket_ids: list[str]) -> list[str]:
    seen, out = set(), []
    for t in ranked_ticket_ids:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def recall_at_k(ranked, gold: set, k):
    return len(set(ranked[:k]) & gold) / len(gold) if gold else 0.0


def precision_at_k(ranked, gold: set, k):
    return len(set(ranked[:k]) & gold) / k if k else 0.0


def mrr(ranked, gold: set):
    for i, t in enumerate(ranked, 1):
        if t in gold:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked, gold: set, k):
    dcg = sum(1 / math.log2(i + 1) for i, t in enumerate(ranked[:k], 1) if t in gold)
    idcg = sum(1 / math.log2(i + 1) for i in range(1, min(len(gold), k) + 1))
    return dcg / idcg if idcg else 0.0


def bootstrap_ci(scores: list[float], metric: callable, n: int = 1000, ci: float = 0.95) -> tuple[float, float]:
    """95% CI by resampling query-level scores with replacement."""
    means = []
    for _ in range(n):
        sample = random.choices(scores, k=len(scores))
        means.append(metric(sample))
    lo = (1 - ci) / 2
    hi = 1 - lo
    return float(statistics.quantiles(means, n=100, method="inclusive")[round(lo * 100)]), float(statistics.quantiles(means, n=100, method="inclusive")[round(hi * 100)])

