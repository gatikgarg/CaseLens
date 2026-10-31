import argparse
import json
from pathlib import Path

from backend.app.agent.graph import agent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="evaluation/datasets/e2e.jsonl")
    args = ap.parse_args()
    rows = [json.loads(l) for l in Path(args.dataset).read_text(encoding="utf-8").splitlines() if l.strip()]
    results = []
    for row in rows:
        state = agent.invoke(
            {
                "question": row["question"],
                "history": [],
                "options": {"mode": "hybrid", "effort": "fast", "top_k": 8},
                "route": "",
                "standalone_question": row["question"],
                "transcript": [],
                "iterations": 0,
                "results": {},
                "charts": [],
                "evidence": [],
                "answer": None,
                "verification": None,
                "repair_attempts": 0,
                "trace": [],
                "tokens_in": 0,
                "tokens_out": 0,
            }
        )
        results.append({"qid": row["qid"], "route": state.get("route"), "verification": state.get("verification")})
    out = Path("evaluation/results/e2e_latest.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

