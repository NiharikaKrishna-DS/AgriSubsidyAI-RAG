"""Search embedded chunks with a plain-text question and show citations."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from scripts.embed import (
    DEFAULT_MODEL,
    DEFAULT_OUTPUT_FOLDER,
    INDEX_FILE_NAME,
    MANIFEST_FILE_NAME,
    METADATA_FILE_NAME,
)


def _load_metadata(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Metadata file does not exist: {path}")
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def search_chunks(
    question: str,
    output_folder: str | Path = DEFAULT_OUTPUT_FOLDER,
    *,
    model_name: str = DEFAULT_MODEL,
    top_k: int = 5,
    model: Any | None = None,
) -> list[dict[str, Any]]:
    """Return the most relevant chunks with provenance citations."""
    if not question.strip():
        raise ValueError("question must not be empty")
    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    output_path = Path(output_folder)
    index = faiss.read_index(str(output_path / INDEX_FILE_NAME))
    metadata = _load_metadata(output_path / METADATA_FILE_NAME)
    manifest = json.loads(
        (output_path / MANIFEST_FILE_NAME).read_text(encoding="utf-8")
    )
    if index.ntotal != len(metadata):
        raise ValueError("FAISS vector count does not match metadata count")
    if manifest["embedding_model"] != model_name:
        raise ValueError(
            "Query model does not match the model used to build the index: "
            f"{manifest['embedding_model']}"
        )

    encoder = model or SentenceTransformer(model_name)
    query_vector = encoder.encode(
        [question],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    scores, positions = index.search(
        np.asarray(query_vector, dtype="float32"),
        min(top_k, index.ntotal),
    )

    results = []
    for score, position in zip(scores[0], positions[0]):
        record = dict(metadata[int(position)])
        record["score"] = float(score)
        record["citation"] = {
            "title": record.get("title"),
            "source_url": record.get("source_url"),
            "section": record.get("section"),
            "chunk_id": record.get("chunk_id"),
        }
        results.append(record)
    return results


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", help="Plain-text question to search")
    parser.add_argument("--output-folder", type=Path, default=DEFAULT_OUTPUT_FOLDER)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    for rank, result in enumerate(
        search_chunks(
            args.question,
            args.output_folder,
            model_name=args.model,
            top_k=args.top_k,
        ),
        start=1,
    ):
        citation = result["citation"]
        print(f"\n{rank}. score={result['score']:.4f}")
        print(result.get("text", "[Text was not stored in metadata]"))
        print(
            "Citation: "
            f"{citation.get('title') or 'Untitled'} | "
            f"{citation.get('section') or 'Unspecified section'} | "
            f"{citation.get('source_url') or 'No source URL'} | "
            f"chunk={citation.get('chunk_id')}"
        )


if __name__ == "__main__":
    main()
