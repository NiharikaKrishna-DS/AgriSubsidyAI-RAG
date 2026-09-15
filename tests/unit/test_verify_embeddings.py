import json

import numpy as np

from scripts.embed import embed_chunks
from scripts.verify_embeddings import verify_index


class FakeEncoder:
    def encode(self, texts, **kwargs):
        vectors = np.asarray(
            [[1.0, 0.0] if "first" in text.lower() else [0.0, 1.0] for text in texts],
            dtype="float32",
        )
        if kwargs.get("normalize_embeddings"):
            vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors


def test_verify_index_checks_counts_alignment_and_vectors(tmp_path):
    chunks_path = tmp_path / "chunks_ready.jsonl"
    chunks_path.write_text(
        "\n".join(
            [
                json.dumps({"chunk_id": "one", "text": "first chunk"}),
                json.dumps({"chunk_id": "two", "text": "second chunk"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "vectorstore"
    embed_chunks(chunks_path, output_path, model_name="fake", model=FakeEncoder())

    result = verify_index(chunks_path, output_path)

    assert result["passed"] is True
    assert result["chunk_count"] == 2
    assert result["vector_count"] == 2
    assert result["normalized_vectors"] is True
