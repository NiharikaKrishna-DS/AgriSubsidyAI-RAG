import json

import numpy as np
import pytest

from scripts.embed import embed_chunks, load_ready_chunks


class FakeEncoder:
    def encode(self, texts, **kwargs):
        assert kwargs["normalize_embeddings"] is True
        assert kwargs["convert_to_numpy"] is True
        return np.asarray([[len(text), 1.0] for text in texts], dtype="float32")


def test_load_ready_chunks_rejects_non_ready_file(tmp_path):
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text('{"text": "not allowed"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="chunks_ready.jsonl"):
        load_ready_chunks(chunks_path)


def test_embed_chunks_uses_only_ready_chunks_and_writes_metadata(tmp_path):
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

    manifest = embed_chunks(
        chunks_path,
        tmp_path / "vectorstore",
        model_name="fake-model",
        model=FakeEncoder(),
    )

    assert manifest["source_file_name"] == "chunks_ready.jsonl"
    assert manifest["chunk_count"] == 2
    assert (tmp_path / "vectorstore" / "chunks.faiss").exists()
    metadata = [
        json.loads(line)
        for line in (tmp_path / "vectorstore" / "chunks_metadata.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert metadata == [
        {"chunk_id": "one", "text": "first chunk"},
        {"chunk_id": "two", "text": "second chunk"},
    ]
