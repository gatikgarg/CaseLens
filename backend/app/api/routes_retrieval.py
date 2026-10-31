from fastapi import APIRouter

from backend.app.retrieval import pipeline as retrieval
from backend.app.schemas.filters import RetrievalDebugRequest, RetrievalDebugResponse, StageHit

router = APIRouter()


def _stage(hits: list) -> list[StageHit]:
    out = []
    for r, h in enumerate(hits, 1):
        out.append(
            StageHit(
                rank=r,
                doc_id=h.id,
                ticket_id=h.ticket_id,
                doc_type=h.doc_type,
                snippet=h.text[:240],
                score=max(h.scores.values()) if h.scores else 0.0,
                scores=h.scores,
            )
        )
    return out


@router.post("/api/retrieval/debug", response_model=RetrievalDebugResponse)
def debug(req: RetrievalDebugRequest) -> RetrievalDebugResponse:
    result = retrieval.inspect(req.query, req.mode, req.top_k, req.do_rewrite, req.do_rerank)
    return RetrievalDebugResponse(
        query=req.query,
        rewrite=result["rewrite"],
        stages={k: _stage(v) for k, v in result["stages"].items()},
        timings_ms=result["timings_ms"],
    )

