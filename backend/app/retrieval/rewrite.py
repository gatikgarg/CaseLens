import json

from backend.app.core.config import get_settings

SYS = """You prepare search queries for a customer-support ticket database.
Return JSON only: {"standalone": str, "variants": [str, str], "filters": {"category": [..], "priority": [..], "project": [..], "created_from": "YYYY-MM-DD"|null, "created_to": "YYYY-MM-DD"|null}}
- standalone: the question rewritten so it needs no chat history.
- variants: 2 alternative phrasings using different vocabulary (synonyms, symptoms vs causes). Do not add facts not implied by the question.
- filters: ONLY if the user explicitly constrained them. Allowed values: {allowed}. Otherwise empty."""


def rewrite(question: str, history: list[dict], allowed: dict) -> dict:
    from backend.app.llm.deepseek import get_llm

    msgs = [
        {"role": "system", "content": SYS.replace("{allowed}", json.dumps(allowed)[:3000])},
        {"role": "user", "content": json.dumps({"history": history[-6:], "question": question})},
    ]
    out = get_llm().chat(msgs, json_mode=True)
    try:
        return json.loads(out.content or "{}")
    except Exception:
        return {"standalone": question, "variants": [], "filters": {}}

