"""Embed only the validated chunks in chunks_ready.jsonl into a FAISS index."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

try:
    from config.settings import settings
except ModuleNotFoundError:
    settings = None


READY_CHUNK_FILE_NAME = "chunks_ready.jsonl"
DEFAULT_CHUNKS_PATH = Path("data/processed") / READY_CHUNK_FILE_NAME
DEFAULT_OUTPUT_FOLDER = Path("data/vectorstore")
DEFAULT_MODEL = (
    settings.EMBEDDING_MODEL
    if settings is not None
    else os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
)
INDEX_FILE_NAME = "chunks.faiss"
METADATA_FILE_NAME = "chunks_metadata.jsonl"
MANIFEST_FILE_NAME = "manifest.json"


def load_ready_chunks(path: str | Path = DEFAULT_CHUNKS_PATH) -> list[dict[str, Any]]:
    """Load validated chunks and reject every other input filename."""
    chunks_path = Path(path)
    if chunks_path.name != READY_CHUNK_FILE_NAME:
        raise ValueError(
            f"Embedding requires {READY_CHUNK_FILE_NAME}; received {chunks_path.name}"
        )
    if not chunks_path.is_file():
        raise FileNotFoundError(f"Ready chunk file does not exist: {chunks_path}")

    chunks: list[dict[str, Any]] = []
    with chunks_path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON in {chunks_path} at line {line_number}"
                ) from error
            if not isinstance(chunk, dict) or not str(chunk.get("text", "")).strip():
                raise ValueError(
                    f"Chunk at line {line_number} in {chunks_path} has no text"
                )
            chunks.append(chunk)
    return chunks


def _metadata(chunk: dict[str, Any]) -> dict[str, Any]:
    """Keep chunk text and provenance so search results can be displayed."""
    return dict(chunk)


def embed_chunks(
    chunks_path: str | Path = DEFAULT_CHUNKS_PATH,
    output_folder: str | Path = DEFAULT_OUTPUT_FOLDER,
    *,
    model_name: str = DEFAULT_MODEL,
    batch_size: int = 32,
    model: Any | None = None,
) -> dict[str, Any]:
    """Create a cosine-similarity FAISS index from chunks_ready.jsonl only."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    chunks = load_ready_chunks(chunks_path)
    if not chunks:
        raise ValueError(f"{READY_CHUNK_FILE_NAME} contains no chunks")

    encoder = model or SentenceTransformer(model_name)
    vectors = encoder.encode(
        [str(chunk["text"]) for chunk in chunks],
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    vectors = np.asarray(vectors, dtype="float32")
    if vectors.ndim != 2 or vectors.shape[0] != len(chunks):
        raise ValueError("Embedding model returned an unexpected vector shape")

    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)
    #the vectors.shape is storing the columns (1) of vector to craete the index with the correct dimension
    index = faiss.IndexFlatIP(vectors.shape[1])
    #add will add the vectors to the index, so that we can search for similar vectors later to RAM
    index.add(vectors)
    index_path = output_path / INDEX_FILE_NAME
    # RAM to Disk, so that we can load the index later without having to re-embed the chunks
    faiss.write_index(index, str(index_path))
     
    metadata_path = output_path / METADATA_FILE_NAME
    with metadata_path.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(json.dumps(_metadata(chunk), ensure_ascii=False) + "\n")
   #because lightweight vector tools like FAISS are actually "blind" to text
    manifest = {
        "source_file": str(Path(chunks_path)),
        "source_file_name": READY_CHUNK_FILE_NAME,
        "embedding_model": model_name,
        "metric": "inner_product_on_normalized_embeddings",
        "dimension": int(vectors.shape[1]),
        "chunk_count": len(chunks),
        "index_file": INDEX_FILE_NAME,
        "metadata_file": METADATA_FILE_NAME,
    }
    manifest_path = output_path / MANIFEST_FILE_NAME
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--output-folder", type=Path, default=DEFAULT_OUTPUT_FOLDER)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    print(
        json.dumps(
            embed_chunks(
                args.chunks,
                args.output_folder,
                model_name=args.model,
                batch_size=args.batch_size,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
