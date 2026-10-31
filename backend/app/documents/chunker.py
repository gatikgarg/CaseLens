import re
from dataclasses import dataclass

from backend.app.core.config import get_settings

_tok = None


def tok():
    global _tok
    if _tok is None:
        try:
            from transformers import AutoTokenizer

            _tok = AutoTokenizer.from_pretrained(get_settings().embed_model)
        except Exception:
            _tok = _FallbackTokenizer()
    return _tok


class _FallbackTokenizer:
    """Offline-safe fallback used only when the HF tokenizer cannot be loaded."""

    def encode(self, s: str, add_special_tokens: bool = False) -> list[int]:
        return list(range(len(re.findall(r"\w+|[^\w\s]", s))))


def n_tokens(s: str) -> int:
    return len(tok().encode(s, add_special_tokens=False))


@dataclass
class Turn:
    seq: int
    role: str | None
    text: str


def chunk_turns(
    turns: list[Turn],
    header: str,
    max_tokens: int = 256,
    overlap_turns: int = 1,
) -> list[tuple[str, list[Turn]]]:
    """Greedy, turn-aligned chunks. Never splits a turn unless it alone exceeds max_tokens."""
    if not turns:
        return []

    chunks: list[tuple[str, list[Turn]]] = []
    cur: list[Turn] = []
    cur_tok = n_tokens(header)

    def flush() -> None:
        if cur:
            body = "\n".join(f"{(t.role or 'speaker')}: {t.text}" for t in cur)
            chunks.append((header + "\n" + body, list(cur)))

    def render(cur: list[Turn]) -> str:
        return header + "\n" + "\n".join(f"{(t.role or 'speaker')}: {t.text}" for t in cur)

    for t in turns:
        tt = n_tokens(t.text)
        if cur and cur_tok + tt > max_tokens:
            flush()
            cur = cur[-overlap_turns:] if overlap_turns else []
            cur_tok = n_tokens(render(cur))
        cur.append(t)
        cur_tok += tt
    flush()
    return chunks

