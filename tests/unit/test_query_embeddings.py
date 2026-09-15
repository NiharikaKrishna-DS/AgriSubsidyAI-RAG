import json

import faiss
import numpy as np

from scripts.query_embeddings import search_chunks


class FakeEncoder:
    def encode(self, texts, **kwargs):
        return np.asarray(
            [[1.0, 0.0] if "first" in text.lower() else [0.0, 1.0] for text in texts],
            dtype="float32",
        )


def test_search_chunks_returns_ranked_results_with_citations(tmp_path):
    output_path = tmp_path / "vectorstore"
    output_path.mkdir()
    index = faiss.IndexFlatIP(2)
    index.add(np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype="float32"))
    faiss.write_index(index, str(output_path / "chunks.faiss"))
    (output_path / "chunks_metadata.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "chunk_id": "first-id",
                        "title": "First scheme",
                        "section": "Benefits",
                        "source_url": "https://example.com/first",
                        "text": "First result text",
                    }
                ),
                json.dumps(
                    {
                        "chunk_id": "second-id",
                        "title": "Second scheme",
                        "section": "Eligibility",
                        "source_url": "https://example.com/second",
                        "text": "Second result text",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (output_path / "manifest.json").write_text(
        json.dumps({"embedding_model": "fake-model"}),
        encoding="utf-8",
    )

    results = search_chunks(
        "first question",
        output_path,
        model_name="fake-model",
        top_k=1,
        model=FakeEncoder(),
    )

    assert len(results) == 1
    assert results[0]["chunk_id"] == "first-id"
    assert results[0]["citation"]["source_url"] == "https://example.com/first"
