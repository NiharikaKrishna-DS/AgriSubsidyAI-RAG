"""Verify a FAISS index built from chunks_ready.jsonl."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from scripts.embed import (
    DEFAULT_CHUNKS_PATH,
    DEFAULT_MODEL,
    DEFAULT_OUTPUT_FOLDER,
    INDEX_FILE_NAME,
    MANIFEST_FILE_NAME,
    METADATA_FILE_NAME,
    load_ready_chunks,
)


def _load_metadata(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Metadata file does not exist: {path}")
    records = []
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Invalid metadata JSON at line {line_number}: {path}"
                    ) from error
    return records


def verify_index(
    chunks_path: str | Path = DEFAULT_CHUNKS_PATH,
    output_folder: str | Path = DEFAULT_OUTPUT_FOLDER,
    *,
    model_name: str = DEFAULT_MODEL,
    model: Any | None = None,
    evaluation_cases: list[dict[str, Any]] | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    """Check index integrity and optionally run semantic retrieval smoke tests."""
    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    chunks = load_ready_chunks(chunks_path)
    output_path = Path(output_folder)
    index_path = output_path / INDEX_FILE_NAME
    manifest_path = output_path / MANIFEST_FILE_NAME
    index = faiss.read_index(str(index_path))
    metadata = _load_metadata(output_path / METADATA_FILE_NAME)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    chunk_ids = [chunk.get("chunk_id") for chunk in chunks]
    metadata_ids = [record.get("chunk_id") for record in metadata]
    if len(set(chunk_ids)) != len(chunk_ids):
        raise ValueError("Ready chunks contain duplicate chunk_id values")
    if chunk_ids != metadata_ids:
        raise ValueError("Metadata order or chunk IDs do not match chunks_ready.jsonl")
    if index.ntotal != len(chunks):
        raise ValueError(
            f"FAISS vector count {index.ntotal} does not match chunk count {len(chunks)}"
        )
    if index.d != int(manifest["dimension"]):
        raise ValueError("FAISS dimension does not match the manifest")

    vectors = index.reconstruct_n(0, index.ntotal)
    norms = np.linalg.norm(vectors, axis=1)
    if not np.isfinite(vectors).all():
        raise ValueError("FAISS index contains NaN or infinite values")
    if np.any(norms <= 0):
        raise ValueError("FAISS index contains a zero-length vector")

    result: dict[str, Any] = {
        "passed": True,
        "chunk_count": len(chunks),
        "vector_count": index.ntotal,
        "dimension": index.d,
        "finite_vectors": True,
        "nonzero_vectors": True,
        "metadata_aligned": True,
        "normalized_vectors": bool(np.allclose(norms, 1.0, atol=1e-3)),
        "semantic_cases": [],
    }

    if evaluation_cases:
        encoder = model or SentenceTransformer(model_name)
        query_vectors = encoder.encode(
            [case["query"] for case in evaluation_cases],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        scores, positions = index.search(
            np.asarray(query_vectors, dtype="float32"),
            min(top_k, index.ntotal),
        )
        ready_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
        for case, case_scores, case_positions in zip(
            evaluation_cases, scores, positions
        ):
            retrieved = [
                ready_by_id[metadata[position]["chunk_id"]]
                for position in case_positions
                if position >= 0
            ]
            source_urls = set(case["relevant_source_urls"])
            source_hit = any(
                chunk.get("source_url") in source_urls for chunk in retrieved
            )
            evidence_hit = any(
                chunk.get("source_url") in source_urls
                and all(
                    term.casefold() in str(chunk.get("text", "")).casefold()
                    for term in case["relevant_terms"]
                )
                for chunk in retrieved
            )
            result["semantic_cases"].append(
                {
                    "id": case["id"],
                    "source_hit": source_hit,
                    "evidence_hit": evidence_hit,
                    "top_score": float(case_scores[0]),
                }
            )
        result["source_hit_rate"] = sum(
            case["source_hit"] for case in result["semantic_cases"]
        ) / len(result["semantic_cases"])
        result["evidence_hit_rate"] = sum(
            case["evidence_hit"] for case in result["semantic_cases"]
        ) / len(result["semantic_cases"])

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--output-folder", type=Path, default=DEFAULT_OUTPUT_FOLDER)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("evaluation/retrieval_eval.json"),
        help="Optional semantic smoke-test cases.",
    )
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    print(
        json.dumps(
            verify_index(
                args.chunks,
                args.output_folder,
                model_name=args.model,
                evaluation_cases=cases,
                top_k=args.top_k,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
