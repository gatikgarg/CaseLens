"""Generate candidate retrieval questions from sampled tickets with conversations.

The generated set still requires manual review (>=30%) before it becomes the
dev/test split. Gold ticket ids are the source tickets; other tickets can also
be valid answers, so recall/precision are lower bounds.
"""
import argparse
import json
import random
from pathlib import Path

from sqlalchemy import text

from backend.app.db.session import SessionLocal
from backend.app.llm.deepseek import get_llm

PROMPT = (
    "You are a support analyst. Given this support ticket text, write 2 questions "
    "a colleague might type to find this ticket later (one symptom-style, one theme-style). "
    "Do not copy distinctive phrases or the ticket id. Return JSON: {\"questions\": [\"..\", \"..\"]}"
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="evaluation/datasets/retrieval_dev.jsonl")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    random.seed(args.seed)

    with SessionLocal() as s:
        rows = s.execute(
            text(
                "SELECT f.ticket_id, t.title, t.description FROM ticket_facts f "
                "JOIN tickets t USING (ticket_id) WHERE f.has_conversation "
                "ORDER BY random() LIMIT :n"
            ),
            {"n": args.n},
        ).mappings().all()

    llm = get_llm()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for i, r in enumerate(rows):
            text = f"{r['title'] or ''}\n{r['description'] or ''}"[:3000]
            try:
                data = json.loads(llm.chat([{"role": "user", "content": PROMPT + "\n\n" + text}], json_mode=True).content or "{}")
            except Exception:
                data = {}
            for j, q in enumerate(data.get("questions", [])):
                f.write(json.dumps({"qid": f"g{i}-{j}", "question": q, "gold_ticket_ids": [r["ticket_id"]], "type": "generated"}) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

