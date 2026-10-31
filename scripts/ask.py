import argparse
import asyncio
import json

from backend.app.agent.graph import agent
from backend.app.api.routes_chat import build_response


async def ask(question: str, effort: str, mode: str, top_k: int) -> None:
    state = await agent.ainvoke(
        {
            "question": question,
            "history": [],
            "options": {"mode": mode, "effort": effort, "top_k": top_k},
            "route": "",
            "standalone_question": question,
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
    resp = build_response("cli", state)
    print(resp.model_dump_json(indent=2))


def retrieve(question: str, mode: str) -> None:
    from backend.app.retrieval import pipeline as retrieval

    class Opts:
        pass

    opts = Opts()
    opts.mode = mode
    opts.top_k = 8
    result = retrieval.inspect(question, mode, 8, do_rewrite=True, do_rerank=True)
    print(json.dumps(result["rewrite"], indent=2))
    for stage, hits in result["stages"].items():
        print(f"\n== {stage} ==")
        for h in hits[:10]:
            print(f"  rank {h.ranks.get(stage, '?')} ticket {h.ticket_id} ({h.doc_type}) scores={ {k: round(v, 3) for k, v in h.scores.items()} }")
            print(f"    {h.text[:120]}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("question", nargs="?")
    p.add_argument("--retrieve", action="store_true")
    p.add_argument("--mode", default="hybrid")
    p.add_argument("--effort", default="fast")
    p.add_argument("--top-k", type=int, default=8)
    args = p.parse_args()
    if args.retrieve:
        retrieve(args.question or "cannot log in", args.mode)
    else:
        asyncio.run(ask(args.question or "How many tickets were created per month?", args.effort, args.mode, args.top_k))

