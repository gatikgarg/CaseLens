import argparse
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

import yaml

from backend.app.retrieval import pipeline as retrieval
from evaluation.metrics import collapse, mrr, ndcg_at_k, precision_at_k, recall_at_k


class _Opts:
    def __init__(self, mode, top_k):
        self.mode = mode
        self.top_k = top_k


def evaluate(config: dict, queries: list[dict]) -> dict:
    top_k = config["defaults"]["top_k"]
    if config["dense"] and config["bm25"]:
        mode = "hybrid"
    elif config["dense"]:
        mode = "dense"
    else:
        mode = "bm25"
    rows = []
    for q in queries:
        t0 = time.perf_counter()
        result = retrieval.search(
            q["question"],
            _Opts(mode, top_k),
            do_rewrite=config["rewrite"] or config["expansion"],
            do_rerank=config["rerank"],
            n_candidates=config["defaults"]["n_candidates"],
        )
        ranked = collapse([h.ticket_id for h in result["hits"]])
        gold = set(q["gold_ticket_ids"])
        rows.append(
            {
                "qid": q["qid"],
                "ranked": ranked,
                "gold": sorted(gold),
                "recall_at_10": recall_at_k(ranked, gold, 10),
                "precision_at_5": precision_at_k(ranked, gold, 5),
                "mrr": mrr(ranked, gold),
                "ndcg_at_10": ndcg_at_k(ranked, gold, 10),
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            }
        )
    return {
        "recall@10": statistics.mean(r["recall_at_10"] for r in rows),
        "precision@5": statistics.mean(r["precision_at_5"] for r in rows),
        "mrr": statistics.mean(r["mrr"] for r in rows),
        "ndcg@10": statistics.mean(r["ndcg_at_10"] for r in rows),
        "latency_p50_ms": statistics.median(r["latency_ms"] for r in rows),
        "latency_p95_ms": statistics.quantiles([r["latency_ms"] for r in rows], n=20)[18],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/eval_retrieval.yaml")
    ap.add_argument("--dataset", default="evaluation/datasets/retrieval_test.jsonl")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    queries = [json.loads(l) for l in Path(args.dataset).read_text(encoding="utf-8").splitlines() if l.strip()]
    results = []
    for ab in cfg["ablations"]:
        metrics = evaluate(ab, queries)
        metrics["id"] = ab["id"]
        results.append(metrics)
        print(ab["id"], metrics)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(f"evaluation/results/retrieval_{ts}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

