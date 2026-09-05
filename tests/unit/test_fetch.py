from pathlib import Path

from ingestion import fetch


class SuccessfulResponse:
    text = "<html><title>Test</title><body><nav>Menu</nav><p>Useful text</p><script>ignore</script></body></html>"
    headers = {"content-type": "text/html"}

    def raise_for_status(self):
        pass


def test_fetch_url_saves_clean_document(monkeypatch, tmp_path):
    monkeypatch.setattr(fetch.requests, "get", lambda url, timeout: SuccessfulResponse())
    monkeypatch.setattr(fetch, "PROCESSED_FOLDER", str(tmp_path))

    url = "https://example.com"
    result = fetch.fetch_url(url)

    expected_file = Path(tmp_path) / f"{fetch.generate_filename(url)}.json"
    assert result["title"] == "Test"
    assert "Useful text" in result["text"]
    assert "Menu" not in result["text"]
    assert "ignore" not in result["text"]
    assert result["links"] == []
    assert expected_file.exists()


def test_crawl_category_collects_scheme_pages(monkeypatch, tmp_path):
    category_html = """
    <a href="/central/first-scheme">Agriculture First</a>
    <a href="/central/second-scheme">Agriculture Second</a>
    <a href="/category/other">Other</a>
    """

    class CategoryResponse(SuccessfulResponse):
        text = category_html

    monkeypatch.setattr(fetch, "PROCESSED_FOLDER", str(tmp_path))
    monkeypatch.setattr(fetch.requests, "get", lambda url, timeout: CategoryResponse())

    documents, pdfs = fetch.crawl_category("https://example.com/category/agriculture")

    assert [document["url"] for document in documents] == [
        "https://example.com/central/first-scheme",
        "https://example.com/central/second-scheme",
    ]
    assert pdfs == []