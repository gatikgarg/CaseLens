"""Usage: python -m backend.app.ingestion.profile data/raw/mendeley_helpdesk_v3"""
import sys
from pathlib import Path

import pandas as pd


def profile_file(path: Path) -> str:
    df = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        na_values=[""],
        low_memory=False,
        encoding_errors="replace",
    )
    out = [
        f"## {path.name}",
        f"- rows: **{len(df):,}**, columns: **{df.shape[1]}**",
        "",
        "| column | non-null % | unique | sample values |",
        "|---|---|---|---|",
    ]
    for c in df.columns:
        s = df[c]
        sample = ", ".join(map(lambda v: repr(v)[:40], s.dropna().unique()[:3]))
        out.append(f"| `{c}` | {100 * s.notna().mean():.1f} | {s.nunique():,} | {sample} |")
    dup = df.duplicated().sum()
    out += ["", f"- exact duplicate rows: {dup:,}", ""]
    return "\n".join(out)


if __name__ == "__main__":
    root = Path(sys.argv[1])
    rep = ["# Dataset profile\n"]
    for p in sorted(root.glob("*.csv")):
        rep.append(profile_file(p))
    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "profile_report.md").write_text("\n".join(rep), encoding="utf-8")
    print("wrote data/processed/profile_report.md")

