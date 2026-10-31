import re

NUM = re.compile(r"(?<![\w.#\[])\d[\d,]*\.?\d*%?")
CITE = re.compile(r"\[((?:E|D)\d+)\]")


def numbers_in(text: str) -> list[float]:
    t = CITE.sub("", text)
    out = []
    for m in NUM.findall(t):
        try:
            out.append(float(m.replace(",", "").rstrip("%")))
        except ValueError:
            pass
    return out


def allowed_numbers(results: dict, evidence: list[dict]) -> set[float]:
    ok: set[float] = set()
    for res in results.values():
        df = res.df
        ok.add(float(len(df)))
        for c in df.select_dtypes("number").columns:
            col = df[c].dropna()
            for v in col:
                ok |= {float(v), round(float(v), 0), round(float(v), 1), round(float(v), 2)}
            tot = col.sum()
            if tot:
                ok |= {round(float(v) / tot * 100, p) for v in col for p in (0, 1)}
            ok |= {float(tot), round(float(col.mean()), 1), round(float(col.max() - col.min()), 1)}
    for e in evidence:
        ok |= set(numbers_in(e["text"]))
    return ok


def verify(answer: dict, results: dict, evidence: list[dict], ticket_id_re: str) -> dict:
    issues: list[str] = []
    text = answer["answer_markdown"]
    valid_refs = set(results) | {e["ref_id"] for e in evidence}
    cited = set(CITE.findall(text)) | {c for f in answer["findings"] for c in f["citations"]}
    for c in cited - valid_refs:
        issues.append(f"citation {c} does not exist")
    for f in answer["findings"]:
        if f["status"] == "verified" and not f["citations"]:
            issues.append(f"verified finding without citation: {f['statement'][:60]}")

    allowed = allowed_numbers(results, evidence)
    for n in numbers_in(text):
        if n <= 10 or 1990 <= n <= 2100:
            continue
        if not any(abs(n - a) <= max(0.005 * abs(a), 0.051) for a in allowed):
            issues.append(f"number {n:g} not found in tool output")

    known_ids = {e["ticket_id"] for e in evidence}
    for tid in set(re.findall(ticket_id_re, text)):
        if tid not in known_ids:
            issues.append(f"ticket id {tid} not in retrieved evidence")
    return {"ok": not issues, "issues": issues}

