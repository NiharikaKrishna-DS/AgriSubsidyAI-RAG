"""Clean, chunk, and validate documents before embedding."""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from bs4 import BeautifulSoup
from pypdf import PdfReader
from transformers import AutoTokenizer

try:
    from config.settings import settings
except ModuleNotFoundError:
    settings = None


DEFAULT_CHUNK_SIZE = 400
DEFAULT_CHUNK_OVERLAP = 64
DEFAULT_MIN_WORDS = 20
DEFAULT_MAX_TOKENS = 512
DEFAULT_EMBEDDING_MODEL = (
    settings.EMBEDDING_MODEL
    if settings is not None
    else os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
)
CHUNK_FILE_NAME = "chunks.jsonl"
READY_CHUNK_FILE_NAME = "chunks_ready.jsonl"
EVALUATION_FILE_NAME = "chunk_evaluation.json"
INSPECTION_FILE_NAME = "chunk_inspection.jsonl"
DEFAULT_INPUT_FOLDER = "data/processed/pdfs"
DEFAULT_OUTPUT_FOLDER = "data/processed"

_WHITESPACE_RE = re.compile(r"[ \t]+")
_TOKEN_RE = re.compile(r"\S+")
_SENTENCE_RE = re.compile(r".+?(?:[.!?]+(?=\s|$)|$)", re.DOTALL)
_BOILERPLATE_REPLACEMENTS = (
    (
        re.compile(
            r"\s*✕?\s*\(\s*https?://\s*(?:whatsapp\.com|\.com/channel|t\.me)[^)]*\)",
            re.IGNORECASE,
        ),
        " ",
    ),
    (
        re.compile(r"\s*https?://(?:whatsapp\.com|t\.me)/\S*", re.IGNORECASE),
        " ",
    ),
    (
        re.compile(
            r"\s*\(\s*https?://\s*(?:api\.)?\.com/send\?[^)]*\)",
            re.IGNORECASE,
        ),
        " ",
    ),
    (
        re.compile(r"\s*\([^)]*schemesinindia\.in[^)]*\)", re.IGNORECASE),
        " ",
    ),
    (
        re.compile(r"\s*https%3A%2F%2Fschemesinindia\.in[^)]*\)?", re.IGNORECASE),
        " ",
    ),
    (
        re.compile(
            r"\s*[✕x]?\s*WhatsApp\s*\([^)]*\)\s*Telegram\s*\([^)]*\)",
            re.IGNORECASE,
        ),
        " ",
    ),
    (re.compile(r"\s*\b(?:WhatsApp|Telegram)\b", re.IGNORECASE), " "),
    (re.compile(r"\bShare\s+on\s*WhatsApp\b", re.IGNORECASE), ""),
    (re.compile(r"\bHelp others find this scheme\b", re.IGNORECASE), ""),
    (
        re.compile(
            r"\bTap a document to mark it as ready\s*[·.]?\s*"
            r"Progress saved automatically\b",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"\bschemesinindia\.in\s*[—-]\s*All Indian Government Schemes\s*",
            re.IGNORECASE,
        ),
        "",
    ),
    (re.compile(r"\b\d+/\d+\s+documents ready\b", re.IGNORECASE), ""),
    (
        re.compile(
            r"\bSG\s+Written\s+(?:and|&)\s+fact-checked\s+by.*?"
            r"How we verify scheme facts\s*\([^)]*\)",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"\b(?:by\s*)?Sanket Ghogare\s*\([^)]*\)\s*·?\s*"
            r"Editor,?\s*Schemes In India\s*"
            r"How we verify scheme facts\s*\([^)]*\)",
            re.IGNORECASE,
        ),
        "",
    ),
    (
        re.compile(
            r"\b(?:by\s*)?Sanket Ghogare\s*\([^)]*\)\s*·?\s*"
            r"Editor,?\s*Schemes In India",
            re.IGNORECASE,
        ),
        "",
    ),
    (re.compile(r"\bHow we verify scheme facts\s*\([^)]*\)", re.IGNORECASE), ""),
    (re.compile(r"\bSanket Ghogare,?\s*Editor\s*\([^)]*\)", re.IGNORECASE), ""),
    (re.compile(r"\bLast verified:\s*[^·|\n]+[·|]?", re.IGNORECASE), ""),
    (re.compile(r"\bSG\s+Written\s+(?:and|&)\s+fact-?checked\b", re.IGNORECASE), ""),
    (re.compile(r"\bLast\s+Verified\s*:?\s*\d{1,2}\s+[A-Za-z]+\s+\d{4}", re.IGNORECASE), ""),
    (re.compile(r"\s*✕\s*", re.IGNORECASE), " "),
)


@dataclass
class ChunkingConfig:
    """Single source of truth for tokenization, chunking, and validation."""
    
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    min_words: int = DEFAULT_MIN_WORDS
    max_tokens: int = DEFAULT_MAX_TOKENS
    tokenizer: Any | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")
        if self.chunk_overlap < 0 or self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be between zero and chunk_size - 1")
        if self.min_words < 0:
            raise ValueError("min_words must not be negative")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be greater than zero")

    def get_tokenizer(self) -> Any:
        if self.tokenizer is None:
            self.tokenizer = _load_tokenizer(DEFAULT_EMBEDDING_MODEL)
        return self.tokenizer


# Comprehensive heading matcher for this document type

# ==============================================================================
# HEADING EXTRACTION REGEX
# ==============================================================================
# Purpose: Detects and validates document headings line-by-line.
# Architecture: Uses a wrapping non-capturing group (?: ...) combined with 
#               re.MULTILINE to enforce full-line validation for each pathway.
# ==============================================================================
_HEADING_RE = re.compile(
    r"^"                                         # Matches the START of any individual line (due to re.MULTILINE)
    r"(?:"                                       # Opens outer NON-CAPTURING GROUP (Groups all logic together without consuming memory)
    
    # --- PATHWAY 1: FAQ / Question Headings ---
    r".+\?\s*$"                                  # .+: Requires at least 1 character of text
                                                 # \?: MANDATORY literal question mark (escaped with backslash)
                                                 # \s*$: Allows optional trailing whitespace up to the end of the line
                                                 
    r"|"                                         # OR operator (The fork in the road between Pathway 1 and Pathway 2)
    
    # --- PATHWAY 2: Structural Prefix Headings ---
    r"(?:How to|Benefits of|Who is|Documents Required|Official|Frequently Asked|Agriculture Infrastructure)" 
                                                 # Inner non-capturing group acting as an OR checklist for valid prefixes
    r".+"                                        # .+: Requires at least one character of text immediately following the prefix
    
    r")"                                         # Closes outer NON-CAPTURING GROUP
    r"$",                                        # Matches the END of any individual line (due to re.MULTILINE)
    
    re.MULTILINE                                 # CRITICAL FLAG: Changes '^' and '$' behavior from matching the 
                                                 # entire string to matching the start/end of each individual line (\n).
)

_FAQ_HEADING_RE = re.compile(r"\?\s*$", re.IGNORECASE)


def _is_faq_heading(heading: str) -> bool:
    """Identify explicit question headings whose short answers should be kept."""
    normalized = heading.strip()
    return bool(
        normalized
        and "whatsapp" not in normalized.lower()
        and "http://" not in normalized.lower()
        and "https://" not in normalized.lower()
        and _FAQ_HEADING_RE.search(normalized)
    )


def clean_text(text: str) -> str:
    """Normalize whitespace, remove known page chrome, and deduplicate lines."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    normalized = unicodedata.normalize("NFKC", text).replace("\xa0", " ").replace("\x00", "")
    cleaned_lines: list[str] = []
    seen_lines: set[str] = set()
    for raw_line in normalized.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = _WHITESPACE_RE.sub(" ", raw_line).strip()
        for pattern, replacement in _BOILERPLATE_REPLACEMENTS:
            line = pattern.sub(replacement, line)
        line = _WHITESPACE_RE.sub(" ", line).strip(" |-")
        if not line:
            continue
        if line in seen_lines:
            continue
        seen_lines.add(line)
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _words(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


@lru_cache(maxsize=4)
def _load_tokenizer(model_name: str):
    """Load the Hugging Face tokenizer used by the selected embedding model."""
    token = settings.HF_TOKEN if settings is not None else os.getenv("HF_TOKEN")
    return AutoTokenizer.from_pretrained(
        model_name,
        token=token,
    )


def _token_count(text: str, tokenizer: Any | None = None) -> int:
    """Count tokens with the selected embedding model tokenizer."""
    tokenizer = tokenizer or _load_tokenizer(DEFAULT_EMBEDDING_MODEL)
    options = {"add_special_tokens": True, "truncation": False}
    try:
        encoded = tokenizer.encode(text, verbose=False, **options)
    except TypeError:
        encoded = tokenizer.encode(text, **options)
    return len(encoded)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _section(
    text: str,
    *,
    heading: str = "",
    page_number: int | None = None,
    section_index: int = 0,
) -> dict[str, Any] | None:
    cleaned = clean_text(text)
    if not cleaned:
        return None
    cleaned_heading = clean_text(heading)
    if "whatsapp" in cleaned_heading.lower() or "http://" in cleaned_heading.lower() or "https://" in cleaned_heading.lower():
        cleaned_heading = ""
    return {
        "heading": cleaned_heading,
        "text": cleaned,
        "page_number": page_number,
        "section_index": section_index,
    }


def extract_html_sections(html: str) -> list[dict[str, Any]]:
    """Extract semantic HTML sections, falling back to the document body."""
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        element.decompose()

    sections: list[dict[str, Any]] = []
    heading = ""
    body_lines: list[str] = []
    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table"]):
        if element.name.startswith("h"):
            if body_lines:
                section = _section(
                    "\n".join(body_lines),
                    heading=heading,
                    section_index=len(sections),
                )
                if section:
                    sections.append(section)
                body_lines = []
            heading = element.get_text(" ", strip=True)
        else:
            text = element.get_text(" ", strip=True)
            if text:
                body_lines.append(text)
    if body_lines:
        section = _section(
            "\n".join(body_lines),
            heading=heading,
            section_index=len(sections),
        )
        if section:
            sections.append(section)
    if sections:
        return sections
    return [section] if (section := _section(soup.get_text("\n"))) else []


def _looks_like_pdf_heading(line: str) -> bool:
    words = line.split()
    return (
        1 <= len(words) <= 12
        and len(line) <= 120
        and (_HEADING_RE.match(line) or line.isupper())
    )


def extract_pdf_sections(path: str | Path) -> list[dict[str, Any]]:
    """Extract PDF pages and split obvious headings while retaining page numbers."""
    sections: list[dict[str, Any]] = []
    reader = PdfReader(str(path))
    #print(reader)
    for page_number, page in enumerate(reader.pages, start=1):
        lines = (page.extract_text() or "").splitlines()
        heading = ""
        body_lines: list[str] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if _looks_like_pdf_heading(line):
                if body_lines:
                    section = _section(
                        "\n".join(body_lines),
                        heading=heading,
                        page_number=page_number,
                        section_index=len(sections),
                    )
                    if section:
                        sections.append(section)
                    body_lines = []
                heading = line
            else:
                body_lines.append(line)
        if body_lines:
            section = _section(
                "\n".join(body_lines),
                heading=heading,
                page_number=page_number,
                section_index=len(sections),
            )
            if section:
                sections.append(section)
    return sections


def _recursive_chunks(
    text: str,
    *,
    prefix: str,
    config: ChunkingConfig,
) -> list[str]:
    """Pack structural text units into tokenizer-bounded overlapping chunks.

    Newline-delimited units are treated as paragraphs or list items. Normal
    prose is then split at sentence boundaries; long units fall back to words
    so the embedding model's token limit is always enforced.
    """
    ## preserve the original text structure by splitting into lines and then sentences
    structural_units: list[str] = []
    for line in (part.strip() for part in text.splitlines()):
        if not line:
            continue
        if re.match(r"^(?:[-*•]|\d+[.)])\s+", line):
            structural_units.append(line)
            continue
        structural_units.extend(
            sentence.strip()
            for sentence in _SENTENCE_RE.findall(line)
            if sentence.strip()
        )

    units: list[str] = []
    for unit in structural_units:
        unit_words = _words(unit)
        if not unit_words:
            continue
        if (
            len(unit_words) <= config.chunk_size
            and _token_count(clean_text(prefix + unit), config.get_tokenizer())
            <= config.max_tokens
        ):
            units.append(unit)
            continue

        units.extend(unit_words)

    chunks: list[str] = []
    start = 0
    while start < len(units):
        end = start
        content_words = 0
        while end < len(units):
            # start at 0 index of list go until last like 0:1 0:2 0:3
            candidate = " ".join(units[start : end + 1])
            candidate_words = content_words + len(_words(units[end]))
            if candidate_words > config.chunk_size:
                break
            if (
                _token_count(clean_text(prefix + candidate), config.get_tokenizer())
                > config.max_tokens
            ):
                break
            content_words = candidate_words
            end += 1
        if end == start:
            raise ValueError(
                "max_tokens is too small for the section heading and one word"
            )
        # when we break from inner while , imagine its 0:2 > max chunk , so though its end+1 = 2, end is still 1 so we append 0:1 to
        chunks.append(" ".join(units[start:end]))
        if end == len(units):
            break
        overlap_words = 0
        #lets say we got 0:5
        overlap_start = end
        while overlap_start > start + 1:
            #counting the words of sentnece in end indices and checking if it is greater than overlap size, if yes then break
            # 0:5 but 0,1,2,3,4 that is slicing is upper cound
            unit_words = len(_words(units[overlap_start - 1]))
            if overlap_words + unit_words > config.chunk_overlap:
                break
            overlap_words += unit_words
            overlap_start -= 1
        start = overlap_start if overlap_start < end else end
    return chunks


def _merge_short_sections(
    sections: list[dict[str, Any]],
    min_words: int,
) -> list[dict[str, Any]]:
    """Combine undersized neighboring sections before creating chunks."""
    merged = [dict(section) for section in sections if section]
    while len(merged) > 1:
        #short index enumerates the copy ( merged) to take first occurance that really has less minimum words
        short_index = next(
            (
                index
                for index, section in enumerate(merged)
                if len(_words(section.get("text", ""))) < min_words
            ),
            None,
        )
        if short_index is None:
            break
        #if problamatic index is last one, then we take the previous one to merge with it, otherwise we take the next one to merge with it
        if short_index < len(merged) - 1:
            first = merged[short_index]
            second = merged[short_index + 1]
        else:
            first = merged[short_index - 1]
            second = merged[short_index]

        first_heading = first.get("heading", "")
        second_heading = second.get("heading", "")
        first_text = first.get("text", "")
        second_text = second.get("text", "")
        combined_text = "\n".join(
            value
            for value in (
                first_text,
                second_heading,
                second_text,
            )
            if value
        )
        combined = {
            **first,
            "heading": first_heading,
            "text": combined_text,
        }
        if short_index < len(merged) - 1:
            merged[short_index : short_index + 2] = [combined]
        else:
            merged[short_index - 1 : short_index + 1] = [combined]
    return merged


def chunk_document(
    document: dict[str, Any],
    *,
    config: ChunkingConfig | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    min_words: int = DEFAULT_MIN_WORDS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    tokenizer: Any | None = None,
) -> list[dict[str, Any]]:
    """Clean one document and split it into structure-aware token-bounded chunks."""
    config = config or ChunkingConfig(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        min_words=min_words,
        max_tokens=max_tokens,
        tokenizer=tokenizer,
    )

    source_url = document.get("url", document.get("source_url", document.get("path", "")))
    title = document.get("title", "")
    if document.get("html"):
        sections = extract_html_sections(document["html"])
    elif document.get("sections"):
        sections = document["sections"]
    else:
        sections = [_section(document.get("text", ""))] if document.get("text") else []
    sections = _merge_short_sections(sections, config.min_words)
    chunks: list[dict[str, Any]] = []
    for section in sections:
        if not section:
            continue
        heading = section.get("heading", "")
        is_faq = _is_faq_heading(heading)
        prefix = f"{heading}\n" if heading else ""
        for text in _recursive_chunks(
            section.get("text", ""),
            prefix=prefix,
            config=config,
        ):
            full_text = clean_text(prefix + text)
            chunk_index = len(chunks)
            chunks.append({
                "chunk_id": f"{_content_hash(str(source_url))[:12]}-{chunk_index:04d}",
                "source_url": source_url,
                "title": title,
                "section": heading,
                "is_faq": is_faq,
                "section_index": section.get("section_index", 0),
                "page_number": section.get("page_number"),
                "chunk_index": chunk_index,
                "text": full_text,
                "word_count": len(_words(full_text)),
                "token_count": _token_count(full_text, config.get_tokenizer()),
                "content_hash": _content_hash(full_text),
            })
    return chunks


def evaluate_chunks(
    chunks: Iterable[dict[str, Any]],
    *,
    config: ChunkingConfig | None = None,
    min_words: int = DEFAULT_MIN_WORDS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    tokenizer: Any | None = None,
) -> dict[str, Any]:
    """Return deterministic quality metrics and invalid chunk identifiers."""
    config = config or ChunkingConfig(
        min_words=min_words,
        max_tokens=max_tokens,
        tokenizer=tokenizer,
    )

    chunk_list = list(chunks)
    content_hashes = {
        id(chunk): chunk.get("content_hash") or _content_hash(str(chunk.get("text", "")))
        for chunk in chunk_list
    }
    duplicate_counts = Counter(content_hashes.values())
    issues_by_chunk: dict[str, list[str]] = {}
    issue_counts: Counter[str] = Counter()

    required_fields = ("chunk_id", "source_url", "title", "chunk_index", "text")
    for position, chunk in enumerate(chunk_list):
        chunk_id = str(chunk.get("chunk_id") or f"position-{position}")
        issues: list[str] = []
        missing = [field for field in required_fields if not chunk.get(field) and chunk.get(field) != 0]
        if missing:
            issues.append("missing_metadata")
            issue_counts["missing_metadata"] += 1

        text = chunk.get("text", "")
        word_count = chunk.get("word_count", len(_words(text)) if isinstance(text, str) else 0)
        token_count = (
            chunk.get("token_count")
            if "token_count" in chunk
            else _token_count(text, config.get_tokenizer()) if isinstance(text, str) else 0
        )
        if not text or not isinstance(text, str):
            issues.append("empty_text")
            issue_counts["empty_text"] += 1
        if word_count < config.min_words and not chunk.get("is_faq", False):
            issues.append("too_short")
            issue_counts["too_short"] += 1
        elif word_count < config.min_words and chunk.get("is_faq", False):
            issue_counts["short_faq_preserved"] += 1
        if token_count > config.max_tokens:
            issues.append("too_long")
            issue_counts["too_long"] += 1
        if duplicate_counts.get(content_hashes[id(chunk)], 0) > 1:
            issues.append("duplicate_text")
            issue_counts["duplicate_text"] += 1

        if issues:
            issues_by_chunk[chunk_id] = sorted(set(issues))

    invalid_ids = sorted(issues_by_chunk)
    return {
        "total_chunks": len(chunk_list),
        "valid_chunks": len(chunk_list) - len(invalid_ids),
        "invalid_chunks": len(invalid_ids),
        "issue_counts": dict(sorted(issue_counts.items())),
        "invalid_chunk_ids": invalid_ids,
        "thresholds": {"min_words": config.min_words, "max_tokens": config.max_tokens},
        "short_faq_policy": "preserve_question_headings",
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "passed": not invalid_ids,
    }


def _load_input_documents(input_path: Path) -> Iterable[dict[str, Any]]:
    """Discover supported files and normalize each into one document shape."""
    pdf_metadata: dict[str, dict[str, Any]] = {}
    files = sorted(path for path in input_path.rglob("*") if path.is_file())

    for path in files:
        if path.suffix.lower() != ".json" or path.name == EVALUATION_FILE_NAME:
            continue
        with path.open(encoding="utf-8") as file:
            value = json.load(file)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and item.get("pdf"):
                    pdf_metadata[Path(item["pdf"]).name] = item
        elif isinstance(value, dict) and any(value.get(field) for field in ("text", "html", "sections")):
            yield value

    for path in files:
        suffix = path.suffix.lower()
        if suffix == ".html":
            yield {
                "path": str(path),
                "title": path.stem,
                "html": path.read_text(encoding="utf-8"),
            }
        elif suffix == ".pdf":
            metadata = pdf_metadata.get(path.name, {})
            yield {
                "path": str(path),
                "url": metadata.get("url", str(path)),
                "title": metadata.get("title", path.stem),
                "sections": extract_pdf_sections(path),
            }


def process_documents(
    input_folder: str | Path = DEFAULT_INPUT_FOLDER,
    output_folder: str | Path | None = None,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    min_words: int = DEFAULT_MIN_WORDS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    tokenizer: Any | None = None,
) -> dict[str, Any]:
    """Discover, normalize, chunk, and evaluate supported source documents."""
    config = ChunkingConfig(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        min_words=min_words,
        max_tokens=max_tokens,
        tokenizer=tokenizer,
    )
    input_path = Path(input_folder)
    output_path = (
        Path(output_folder)
        if output_folder
        else Path(DEFAULT_OUTPUT_FOLDER) if input_path == Path(DEFAULT_INPUT_FOLDER) else input_path
    )
    output_path.mkdir(parents=True, exist_ok=True)

    chunks: list[dict[str, Any]] = []
    for document in _load_input_documents(input_path):
        chunks.extend(chunk_document(document, config=config))

    evaluation = evaluate_chunks(
        chunks,
        config=config,
    )
    chunks_path = output_path / CHUNK_FILE_NAME
    with chunks_path.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    invalid_ids = set(evaluation["invalid_chunk_ids"])
    ready_chunks_path = output_path / READY_CHUNK_FILE_NAME
    with ready_chunks_path.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            if chunk["chunk_id"] not in invalid_ids:
                file.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    evaluation["ready_chunks"] = evaluation["valid_chunks"]
    evaluation["embedding_model"] = DEFAULT_EMBEDDING_MODEL
    evaluation["chunks_file"] = str(chunks_path)
    evaluation["ready_chunks_file"] = str(ready_chunks_path)
    inspection_path = output_path / INSPECTION_FILE_NAME
    sample_size = min(25, len(chunks))
    if sample_size:
        step = max(1, len(chunks) // sample_size)
        inspection_chunks = chunks[::step][:sample_size]
    else:
        inspection_chunks = []
    with inspection_path.open("w", encoding="utf-8") as file:
        for chunk in inspection_chunks:
            file.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    evaluation["inspection_file"] = str(inspection_path)
    evaluation["inspection_sample_size"] = len(inspection_chunks)
    evaluation_path = output_path / EVALUATION_FILE_NAME
    with evaluation_path.open("w", encoding="utf-8") as file:
        json.dump(evaluation, file, ensure_ascii=False, indent=2)
    return evaluation


if __name__ == "__main__":
    result = process_documents()
    print(json.dumps(result, indent=2))
