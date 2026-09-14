from evaluation.retrieval_eval import evaluate_corpus


def test_evaluate_corpus_reports_source_and_evidence_coverage():
    cases = [
        {
            "id": "case-1",
            "relevant_source_urls": ["https://example.com/a"],
            "relevant_terms": ["3% subsidy", "CGTMSE"],
        },
        {
            "id": "case-2",
            "relevant_source_urls": ["https://example.com/missing"],
            "relevant_terms": ["not present"],
        },
    ]
    chunks = [
        {
            "source_url": "https://example.com/a",
            "text": "The benefit is a 3% subsidy with CGTMSE support.",
        }
    ]

    result = evaluate_corpus(cases, chunks)

    assert result["case_count"] == 2
    assert result["chunk_count"] == 1
    assert result["source_url_coverage"] == 0.5
    assert result["evidence_case_coverage"] == 0.5
    assert result["cases"][0]["evidence_chunk_count"] == 1
