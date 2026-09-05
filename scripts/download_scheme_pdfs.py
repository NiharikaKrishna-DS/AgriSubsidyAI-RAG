import json
import re
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


CATEGORY_URL = "https://schemesinindia.in/category/agriculture"
OUTPUT_FOLDER = Path("data/processed/pdfs")


def collect_scheme_urls(page):
    page.goto(CATEGORY_URL, wait_until="networkidle")
    links = page.locator('a[href*="/central/"]').filter(has_text=re.compile("Agriculture", re.IGNORECASE))
    return sorted({urljoin(page.url, link.get_attribute("href")) for link in links.all()})


def download_scheme_pdfs(category_url=CATEGORY_URL):
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    results = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(category_url, wait_until="networkidle")
        links = page.locator('a[href*="/central/"]').filter(has_text=re.compile("Agriculture", re.IGNORECASE))
        scheme_urls = sorted({urljoin(page.url, link.get_attribute("href")) for link in links.all()})

        for scheme_url in scheme_urls:
            page.goto(scheme_url, wait_until="networkidle")
            slug = scheme_url.rstrip("/").rsplit("/", 1)[-1]
            pdf_path = OUTPUT_FOLDER / f"{slug}.pdf"
            page.pdf(path=str(pdf_path), format="A4", print_background=True)
            results.append({"url": scheme_url, "title": page.title(), "pdf": str(pdf_path)})

        browser.close()

    metadata_path = OUTPUT_FOLDER / "agriculture_schemes.json"
    metadata_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"schemes={len(results)}")
    print(f"metadata={metadata_path}")
    return results


if __name__ == "__main__":
    download_scheme_pdfs()