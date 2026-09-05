import hashlib
import json
import os
from collections import deque
from urllib.parse import urldefrag, urljoin, urlparse

import requests
import yaml
from bs4 import BeautifulSoup

from services.logger import logger

SOURCE_FILE = "config/sources.yaml"
PROCESSED_FOLDER = "data/processed"
PDF_FOLDER = "data/processed/pdfs"
MAX_PAGES_PER_SOURCE = 25
REQUEST_TIMEOUT = 30
SKIP_EXTENSIONS = {".7z", ".csv", ".doc", ".docx", ".jpg", ".jpeg", ".mp3", ".mp4", ".pdf", ".png", ".rar", ".svg", ".zip"}

os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)

def load_sources():
    with open(SOURCE_FILE,"r",encoding='utf-8') as f:
        return yaml.safe_load(f)["sources"]

def generate_filename(url):
    return hashlib.md5(url.encode()).hexdigest()[:12] 


def extract_document(html, url):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""

    for element in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        element.decompose()

    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    links = [urljoin(url, link.get("href")) for link in soup.find_all("a", href=True)]

    return {"url": url, "title": title, "text": text, "links": links}


def save_document(document):
    filename = generate_filename(document["url"]) + ".json"
    filepath = os.path.join(PROCESSED_FOLDER, filename)
    with open(filepath, encoding="utf-8", mode="w") as file:
        json.dump(document, file, ensure_ascii=False, indent=2)
    return filename


def download_pdf(url):
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "pdf" not in content_type and not urlparse(url).path.lower().endswith(".pdf"):
        return None

    filename = generate_filename(url) + ".pdf"
    filepath = os.path.join(PDF_FOLDER, filename)
    with open(filepath, "wb") as file:
        file.write(response.content)
    logger.info(f"success | {url} | saved = {filename}")
    return filepath


def is_crawlable_url(url):
    parsed_url = urlparse(url)
    return "{{" not in url and not any(parsed_url.path.lower().endswith(extension) for extension in SKIP_EXTENSIONS)


def crawl_category(category_url):
    """Fetch every scheme listed in a category and download direct PDF links."""
    response = requests.get(category_url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    category_domain = urlparse(category_url).netloc
    scheme_urls = {
        urljoin(category_url, anchor["href"])
        for anchor in soup.find_all("a", href=True)
        if urlparse(urljoin(category_url, anchor["href"])).netloc == category_domain
        and urlparse(urljoin(category_url, anchor["href"])).path.startswith("/central/")
        and "agriculture" in anchor.get_text(" ", strip=True).lower()
    }

    documents = []
    pdfs = []
    for scheme_url in sorted(scheme_urls):
        document = fetch_url(scheme_url)
        if document is None:
            continue
        documents.append(document)
        for link in document["links"]:
            if urlparse(link).path.lower().endswith(".pdf"):
                downloaded = download_pdf(link)
                if downloaded:
                    pdfs.append(downloaded)

    logger.info(f"category complete | {category_url} | schemes = {len(documents)} | pdfs = {len(pdfs)}")
    return documents, pdfs


def fetch_url(url):

    try:
      response = requests.get(url, timeout=REQUEST_TIMEOUT)

      response.raise_for_status()
      content_type = response.headers.get("content-type", "text/html").lower()
      if "html" not in content_type:
          logger.info(f"skipped | {url} | content-type = {content_type}")
          return None
      document = extract_document(response.text, url)
      filename = save_document(document)

      logger.info(f"success | {url} | saved = {filename}")
      return document


    except Exception as ex:

      logger.error(
         f"failed | {url} | {str(ex)}"
      )

      return None


def crawl_source(start_url, max_pages=MAX_PAGES_PER_SOURCE):
    """Fetch linked HTML pages on the same domain and store cleaned documents."""
    domain = urlparse(start_url).netloc
    pending = deque([start_url])
    visited = set()
    documents = []

    while pending and len(documents) < max_pages:
        current_url, _ = urldefrag(pending.popleft())
        parsed_url = urlparse(current_url)
        if current_url in visited or parsed_url.netloc != domain or not is_crawlable_url(current_url):
            continue
        visited.add(current_url)

        document = fetch_url(current_url)
        if document is None:
            continue
        documents.append(document)

        for link in document["links"]:
            clean_link, _ = urldefrag(link)
            if (
                urlparse(clean_link).netloc == domain
                and clean_link not in visited
                and is_crawlable_url(clean_link)
            ):
                pending.append(clean_link)

    return documents



def main():
    sources = load_sources()

    for source in sources:
        if source["url"] == "https://schemesinindia.in/":
            crawl_category("https://schemesinindia.in/category/agriculture")
        else:
            crawl_source(source["url"])

if __name__ == "__main__":
    main()