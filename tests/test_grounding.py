from types import SimpleNamespace

import pandas as pd

from backend.app.agent.grounding import verify


def _answer(md, findings, citations=None):
    return {"answer_markdown": md, "findings": findings}


def test_verified_finding_needs_citation():
    out = verify(
        _answer("3 tickets", [{"statement": "x", "status": "verified", "citations": []}]),
        {"D1": SimpleNamespace(df=pd.DataFrame({"x": [1, 2, 3]}))},
        [],
        r"\b[A-Za-z]{1,8}-\d{1,12}\b",
    )
    assert not out["ok"]
    assert any("without citation" in i for i in out["issues"])


def test_invented_number_is_flagged():
    out = verify(
        _answer("There were 999 tickets [D1].", []),
        {"D1": SimpleNamespace(df=pd.DataFrame({"x": [1, 2, 3]}))},
        [],
        r"\b[A-Za-z]{1,8}-\d{1,12}\b",
    )
    assert not out["ok"]
    assert any("999" in i for i in out["issues"])


def test_present_number_passes():
    out = verify(
        _answer("There were 3 tickets [D1].", [{"statement": "3 tickets", "status": "verified", "citations": ["D1"]}]),
        {"D1": SimpleNamespace(df=pd.DataFrame({"x": [1, 2, 3]}))},
        [],
        r"\b[A-Za-z]{1,8}-\d{1,12}\b",
    )
    assert out["ok"]

