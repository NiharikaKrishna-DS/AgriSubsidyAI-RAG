"""Run the lightweight retrieval-evaluation corpus checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def evaluate_corpus(
    cases: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Measure evaluation-case source and evidence coverage in a chunk corpus."""
    results: list[dict[str, Any]] = []
    for case in cases:
        source_urls = set(case["relevant_source_urls"])
        source_chunks = [
            chunk for chunk in chunks if chunk.get("source_url") in source_urls
        ]
        evidence_chunks = [
            chunk
            for chunk in source_chunks
            if all(
                term.casefold() in str(chunk.get("text", "")).casefold()
                for term in case["relevant_terms"]
            )
        ]
        results.append(
            {
                "id": case["id"],
                "source_url_found": bool(source_chunks),
                "evidence_found": bool(evidence_chunks),
                "source_chunk_count": len(source_chunks),
                "evidence_chunk_count": len(evidence_chunks),
            }
        )

    case_count = len(results)
    return {
        "case_count": case_count,
        "chunk_count": len(chunks),
        "source_url_coverage": (
            sum(result["source_url_found"] for result in results) / case_count
            if case_count
            else 0.0
        ),
        "evidence_case_coverage": (
            sum(result["evidence_found"] for result in results) / case_count
            if case_count
            else 0.0
        ),
        "average_source_chunks": (
            sum(result["source_chunk_count"] for result in results) / case_count
            if case_count
            else 0.0
        ),
        "average_evidence_chunks": (
            sum(result["evidence_chunk_count"] for result in results) / case_count
            if case_count
            else 0.0
        ),
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("evaluation/retrieval_eval.json"),
    )
    parser.add_argument(
        "--chunks",
        type=Path,
        default=Path("data/processed/chunks_ready.jsonl"),
    )
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    chunks = [
        json.loads(line)
        for line in args.chunks.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    print(json.dumps(evaluate_corpus(cases, chunks), indent=2))


if __name__ == "__main__":
    main()
