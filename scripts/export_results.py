import json
from pathlib import Path


def export(src: str = "evaluation/results", dst: str = "data/processed/eval_summary.md") -> None:
    rows = []
    for p in sorted(Path(src).glob("retrieval_*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        rows.append(data)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"exported {len(rows)} result files to {dst}")


if __name__ == "__main__":
    export()

