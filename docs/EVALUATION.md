# CaseLens — Evaluation

> Rule: tune on dev, report on test. Never report numbers on data you tuned
> against. Fill this file after Phase 12 runs.

## Dataset construction

- `retrieval_dev.jsonl` / `retrieval_test.jsonl`: 150/150 questions with
  `gold_ticket_ids`, generated from tickets with conversations and manually
  reviewed (≥30%), plus hand-written questions.
- `analytics.jsonl`: 30–40 hand-written `{qid, question, expected_args,
  golden_sql, expected_result}`.
- `e2e.jsonl`: 40–60 mixed questions including unanswerable/out-of-scope.

Limitation: other tickets can also be valid answers, so recall/precision are
lower bounds. Synthetic questions that reuse source wording inflate BM25; we
filter high-lexical-overlap questions.

## Retrieval ablation matrix

| ID | Dense | BM25 | Fusion | Rewrite | Expansion | Rerank |
|---|---|---|---|---|---|---|
| R1 | ✓ | | | | | |
| R2 | | ✓ | | | | |
| R3 | ✓ | ✓ | RRF | | | |
| R4 | ✓ | ✓ | Qdrant RRF | | | |
| R5 | ✓ | ✓ | RRF | | | ✓ |
| R6 | ✓ | ✓ | RRF | ✓ | | ✓ |
| R7 | ✓ | ✓ | RRF | ✓ | ✓ | ✓ |

_Results to be filled by `python -m evaluation.run_retrieval_eval`._

## Headline finding

_To be filled — e.g. "hybrid+rerank improved MRR from X to Y, +Z% latency"._

## Negative result

_To be filled — at least one thing that did not help._

## Failure analysis

_To be filled — 10 bad cases categorized (vocabulary mismatch, missing filter,
over-aggressive rewrite, …)._

## Generation metrics

Faithfulness, answer relevance, citation accuracy, abstention correctness,
numeric grounding, latency, and cost are reported by
`python -m evaluation.run_e2e_eval`. Judge–human agreement is reported where
hand labels exist.

