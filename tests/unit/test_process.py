import json

from ingestion.process import (
    chunk_document,
    clean_text,
    evaluate_chunks,
    extract_html_sections,
    process_documents,
)


class FakeTokenizer:
    def encode(self, text, *, add_special_tokens, truncation):
        assert add_special_tokens is True
        assert truncation is False
        return list(range(len(text.split()) * 2))


def test_clean_text_normalizes_and_deduplicates_lines():
    assert clean_text("  Heading  \r\nBody\xa0 text\nHeading\n\nBody text") == "Heading\nBody text"


def test_clean_text_removes_page_boilerplate_but_keeps_official_links():
    text = (
        "Scheme details ✕ WhatsApp(https://whatsapp.com/channel/example) "
        "Telegram(https://t.me/example) 0/7 documents ready "
        "Official Portal https://agriinfra.dac.gov.in "
        "Sanket Ghogare, Editor (/about) Last verified: 24 May 2026 SG Written & fact-check"
    )

    cleaned = clean_text(text)

    assert "WhatsApp" not in cleaned
    assert "Telegram" not in cleaned
    assert "Sanket Ghogare" not in cleaned
    assert "Official Portal https://agriinfra.dac.gov.in" in cleaned


def test_chunk_document_preserves_provenance_and_overlap():
    document = {"url": "https://example.com/scheme", "title": "Scheme", "text": " ".join(f"word{i}" for i in range(10))}

    chunks = chunk_document(document, chunk_size=6, chunk_overlap=2, tokenizer=FakeTokenizer())

    assert chunks[0]["source_url"] == document["url"]
    assert chunks[0]["title"] == "Scheme"
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["text"].split()[-2:] == chunks[1]["text"].split()[:2]


def test_chunking_preserves_sentence_boundaries_when_units_fit():
    document = {
        "url": "https://example.com/scheme",
        "title": "Scheme",
        "text": "First eligibility rule applies. Second benefit is paid annually. "
        "Third document is required.",
    }

    chunks = chunk_document(
        document,
        chunk_size=20,
        chunk_overlap=0,
        max_tokens=12,
        tokenizer=FakeTokenizer(),
    )

    assert [chunk["text"] for chunk in chunks] == [
        "First eligibility rule applies.",
        "Second benefit is paid annually.",
        "Third document is required.",
    ]


def test_html_chunking_keeps_heading_context():
    html = "<h1>Eligibility</h1><p>" + " ".join(["farmer"] * 20) + "</p>"

    sections = extract_html_sections(html)
    chunks = chunk_document(
        {"url": "https://example.com/scheme", "title": "Scheme", "html": html},
        chunk_size=50,
        chunk_overlap=5,
        tokenizer=FakeTokenizer(),
    )

    assert sections[0]["heading"] == "Eligibility"
    assert chunks[0]["section"] == "Eligibility"
    assert chunks[0]["text"].startswith("Eligibility")


def test_recursive_fallback_keeps_section_context():
    chunks = chunk_document(
        {
            "url": "https://example.com/scheme",
            "title": "Scheme",
            "sections": [{"heading": "Benefits", "text": " ".join(["benefit"] * 12), "section_index": 0}],
        },
        chunk_size=6,
        chunk_overlap=2,
        tokenizer=FakeTokenizer(),
    )

    assert len(chunks) == 3
    assert all(chunk["section"] == "Benefits" for chunk in chunks)


def test_chunk_document_respects_max_tokens():
    chunks = chunk_document(
        {
            "url": "https://example.com/scheme",
            "title": "Scheme",
            "text": " ".join(["word"] * 30),
        },
        chunk_size=100,
        chunk_overlap=10,
        max_tokens=12,
        tokenizer=FakeTokenizer(),
    )

    assert all(chunk["token_count"] <= 12 for chunk in chunks)


def test_short_faq_answer_is_preserved():
    chunks = chunk_document(
        {
            "url": "https://example.com/faq",
            "title": "FAQ",
            "sections": [{"heading": "Who is eligible?", "text": "Small farmers.", "section_index": 0}],
        },
        min_words=20,
        tokenizer=FakeTokenizer(),
    )

    result = evaluate_chunks(chunks, min_words=20, tokenizer=FakeTokenizer())

    assert chunks[0]["is_faq"] is True
    assert result["valid_chunks"] == 1
    assert result["issue_counts"]["short_faq_preserved"] == 1


def test_evaluate_chunks_reports_quality_issues():
    chunks = [
        {
            "chunk_id": "valid",
            "source_url": "https://example.com",
            "title": "Title",
            "chunk_index": 0,
            "text": " ".join(["valid"] * 20),
            "word_count": 20,
            "token_count": 20,
            "content_hash": "same",
        },
        {
            "chunk_id": "duplicate",
            "source_url": "https://example.com",
            "title": "Title",
            "chunk_index": 1,
            "text": "duplicate",
            "word_count": 1,
            "token_count": 1,
            "content_hash": "same",
        },
    ]

    result = evaluate_chunks(chunks)

    assert result["passed"] is False
    assert result["invalid_chunks"] == 2
    assert result["issue_counts"]["duplicate_text"] == 2
    assert result["issue_counts"]["too_short"] == 1


def test_token_count_uses_embedding_tokenizer():
    result = evaluate_chunks(
        [{"chunk_id": "chunk", "source_url": "url", "title": "title", "chunk_index": 0, "text": "one two"}],
        tokenizer=FakeTokenizer(),
        max_tokens=3,
    )

    assert result["issue_counts"]["too_long"] == 1


def test_process_documents_writes_chunks_and_report(tmp_path):
    document_path = tmp_path / "document.json"
    document_path.write_text(
        json.dumps(
            {
                "url": "https://example.com",
                "title": "Title",
                "text": " ".join(["content"] * 25),
            }
        ),
        encoding="utf-8",
    )

    result = process_documents(tmp_path, chunk_size=25, chunk_overlap=5)

    assert result["total_chunks"] == 1
    assert (tmp_path / "chunks.jsonl").exists()
    assert (tmp_path / "chunks_ready.jsonl").exists()
    assert (tmp_path / "chunk_evaluation.json").exists()
    assert (tmp_path / "chunk_inspection.jsonl").exists()
