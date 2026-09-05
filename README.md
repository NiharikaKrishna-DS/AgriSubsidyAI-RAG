# AgriSubsidyAI

**An agentic hybrid Retrieval-Augmented Generation (RAG) system to help farmers discover and understand agricultural subsidy schemes.**

---

## Status: Architecture and initial development

This project is currently in the **architecture and initial development stage**. No end-to-end pipeline, trained models, deployed application, or evaluated results exist yet. Sections describing capabilities describe **planned** behavior unless explicitly marked as implemented.

> This is an independent educational project. It is not affiliated with or endorsed by any government department.

---

## ⚠️ Important Disclaimer

AgriSubsidyAI is a **personal learning and portfolio project**. It is designed to help farmers and researchers explore publicly available information about agricultural subsidy schemes in an easier, conversational format.

- This system **does not** determine, guarantee, or certify eligibility for any scheme.
- This system **is not** an official government service and has **no official government affiliation or endorsement**.
- All answers are grounded in cited sources, but sources may be incomplete, outdated, or third-party in nature.
- **Final eligibility, application status, and approval must always be verified with the responsible government department.**

---

## Project Overview

Agricultural subsidy information in India (and similar contexts) is often published across many disconnected webpages, notifications, FAQs, and — eventually — PDF documents, using varying formats, terminology, and languages. Farmers frequently do not have the time, technical familiarity, or language support needed to search, cross-reference, and interpret these sources.

AgriSubsidyAI aims to be a **RAG-based conversational assistant** that:

- Collects information from trusted public sources
- Detects when source content changes
- Builds structured (database) and unstructured (vector) knowledge stores from that content
- Uses an agentic orchestrator to route farmer questions to the right retrieval strategy
- Explains potentially relevant schemes in plain, cited, multilingual language

This is a **learning project** built to practice real-world RAG system design, agent orchestration, hybrid retrieval, and responsible AI patterns — not a production government tool.

---

## Problem Statement

- Scheme information is scattered across many government and non-government webpages.
- Terminology is often legal/bureaucratic and hard for a layperson to parse.
- Farmers may not find information in their preferred language.
- There is no single, farmer-friendly conversational interface that cites its sources and clearly separates "official" from "secondary" information.
- Existing search tools do not track when scheme information has changed or become outdated.

---

## Project Objectives

- Practice building an **agentic, hybrid RAG** architecture (structured + unstructured retrieval).
- Build a **source-aware ingestion pipeline** with change detection and freshness metadata.
- Design an **orchestrator** capable of routing between database search, knowledge search, hybrid search, and clarification.
- Apply **no-hallucination and grounded-answer principles** throughout the system.
- Explore **multilingual query and response handling** as a planned capability.
- Produce a well-documented, portfolio-quality open-source project.

---

## Current Status

**What exists today:** architecture design, planned repository layout, and this documentation.

**What does NOT exist yet:**

- No production deployment
- No completed ingestion pipeline
- No populated database or vector index
- No tested language support
- No evaluation results or accuracy figures
- No government partnerships or endorsements
- No live demo

Anything not explicitly listed under "Current Status" should be assumed to be **planned, not built**.

---

## Planned Capabilities

> All items below are **planned**, not implemented, unless noted otherwise.

- Ingest public agriculture scheme webpages and track content freshness
- Extract structured scheme fields into a local database
- Build a searchable vector index of unstructured scheme content
- Route farmer questions through an agentic orchestrator
- Support hybrid (keyword + semantic, structured + unstructured) retrieval
- Ask clarification questions when key farmer details are missing
- Generate grounded, cited, plain-language answers
- Support multiple Indian languages (TODO: languages to be confirmed after testing)
- Disclose conflicting or outdated source information
- Provide a simple chat-style UI (Streamlit) backed by an API (FastAPI)

---

## High-Level Architecture

```mermaid
flowchart TB
    subgraph Sources["Public Sources"]
        GOV["Government Domains (gov.in, nic.in)"]
        SEC["Trusted Secondary / Discovery Sources"]
        PDF["Future: PDF Documents"]
    end

    subgraph Ingestion["Ingestion Pipeline (Planned)"]
        CRAWL["Crawler / Loader"]
        CLEAN["Content Cleaning & Change Detection"]
    end

    subgraph Storage["Data Layer (Planned)"]
        RAW["Raw Data Store"]
        SQLITE["SQLite: Structured Scheme Records"]
        FAISS["FAISS: Vector Index"]
    end

    subgraph App["Application Layer (Planned)"]
        ORCH["Orchestrator / Agents"]
        API["FastAPI Backend"]
        UI["Streamlit UI"]
    end

    GOV --> CRAWL
    SEC --> CRAWL
    PDF --> CRAWL
    CRAWL --> CLEAN
    CLEAN --> RAW
    CLEAN --> SQLITE
    CLEAN --> FAISS

    SQLITE --> ORCH
    FAISS --> ORCH
    ORCH --> API
    API --> UI
```

---

## Query and Orchestration Flow

```mermaid
flowchart TD
    Q["User Question"] --> LANG["Language and Intent Analysis"]
    LANG --> ORCH["Orchestrator"]

    ORCH --> CLARIFY["Clarification Agent"]
    ORCH --> DB["Database Agent"]
    ORCH --> RAG["Knowledge RAG Agent"]
    ORCH --> HYBRID["Hybrid Retrieval"]

    CLARIFY --> EVAL["Evidence Validation and Ranking"]
    DB --> EVAL
    RAG --> EVAL
    HYBRID --> EVAL

    EVAL --> GEN["Answer Generation"]
    GEN --> RESP["Plain-Language Response with Citations and Freshness Details"]
```

### Orchestrator Responsibilities (Planned)

The orchestrator is intended to analyze:

- User intent
- User language
- Conversation context
- Available farmer information (state, district, farming activity, etc.)
- Missing information
- Required retrieval path

Based on this analysis, it should select one route:

| Route | Purpose |
|---|---|
| `database` | Deterministic filtering of structured scheme fields |
| `knowledge` | Semantic/document search for explanations and details |
| `hybrid` | Combination of structured filtering and knowledge search |
| `clarification` | Ask the farmer for missing information |
| `unsupported` | Question is outside scope (e.g., unrelated topic) |

---

## Retrieval Route Examples

> These are illustrative design examples, not logged outputs from a working system.

**Example 1 — Database route**
- Question: *"List irrigation subsidy schemes available in Karnataka."*
- Reasoning: This is a structured filter (category + state), answerable from scheme records.
- Route: `database`

**Example 2 — Knowledge route**
- Question: *"Explain this subsidy in simple language."*
- Reasoning: Requires unstructured explanation from scheme description text.
- Route: `knowledge`

**Example 3 — Hybrid route**
- Question: *"Which schemes apply to a small farmer in Karnataka, and what documents do I need?"*
- Reasoning: Needs structured filtering (state, farmer category) **and** unstructured detail (document requirements).
- Route: `hybrid`

**Example 4 — Clarification route**
- Question: *"Am I eligible for a subsidy?"*
- Reasoning: No state, farming activity, or category provided — insufficient information to retrieve anything meaningful.
- Route: `clarification`

---

## Hybrid Search Explanation

AgriSubsidyAI is planned to implement hybrid retrieval at **two levels**.

### Level 1 — Search Hybridization

- **Keyword search** for exact scheme names, identifiers, and domain-specific terms
- **Vector search** for semantic and natural-language similarity
- **Ranking or reranking** of combined keyword and vector results

### Level 2 — Data-Source Hybridization

- **SQLite search** for deterministic, structured filtering (state, category, farmer type, etc.)
- **RAG knowledge search** for explanations, eligibility nuances, and detailed conditions
- **Combined evidence** when a question requires both structured filters and unstructured explanation

---

## Data Ingestion and Freshness Flow

```mermaid
flowchart TD
    A["Registered Source"] --> B["Download or Crawl"]
    B --> C["Validate HTTP Response"]
    C --> D["Extract Main Content"]
    D --> E["Remove Navigation, Ads, Duplicate Text"]
    E --> F["Generate Content Hash"]
    F --> G["Compare With Previous Hash"]
    G -->|Unchanged| H["Skip Reprocessing"]
    G -->|Changed| I["Clean, Chunk, Embed, and Update"]
    I --> J["Update Vector Store"]
    I --> K["Extract Valid Structured Fields"]
    K --> L["Update SQLite Records"]
    L --> M["Write Ingestion History and Logs"]
    H --> M
```

Change detection confirms only whether **downloaded content has changed since the last successful crawl**. It does **not** and cannot guarantee that a publisher or government body has kept the underlying information correct, complete, or current.

---

## Source Trust and Verification Model

- **Government domains** (e.g., `gov.in`, `nic.in`) are treated as **primary sources**.
- **Trusted public or third-party websites** (e.g., `schemesinindia.in`) are treated as **secondary discovery sources** — useful for finding schemes, but not authoritative for final eligibility.
- Secondary-source eligibility details should, wherever possible, be **cross-verified against an official source** before being presented with confidence.
- **No source is labeled "trusted" or "official" unless its status has been explicitly verified.**
- Every indexed source is planned to record:
  - Source URL
  - Publisher type (government / secondary / unknown)
  - Date last checked
  - Freshness / change-detection metadata

PDF and other document ingestion (notifications, circulars, forms) may be added in a later phase.

---

## Raw, Processed, Structured, and Vector Data Layers

| Layer | Contents | Purpose |
|---|---|---|
| **Raw data** | Original downloaded HTML / future source documents | Auditing, debugging, reprocessing |
| **Processed data** | Cleaned content, chunked text, source metadata | Input to embedding and extraction steps |
| **Structured data** | Validated scheme fields in SQLite | Deterministic filtering and lookups |
| **Vector data** | Embeddings + metadata in FAISS | Semantic search over unstructured content |
| **Ingestion metadata** | Source URL, HTTP status, last-checked date, content hash, change-detection status, ingestion result | Freshness tracking and pipeline observability |

---

## Planned Repository Structure

```
AgriSubsidyAI-RAG/
├── README.md
├── requirements.txt
├── .env.example
├── LICENSE
├── .gitignore
├── config/            # Environment, model provider, and app configuration
├── docs/              # Additional design docs, diagrams, notes
├── data/
│   ├── raw/           # Original downloaded source content
│   ├── processed/     # Cleaned & chunked content with metadata
│   ├── database/      # SQLite database file(s)
│   ├── vectorstore/   # FAISS index files
│   └── metadata/      # Ingestion history, source registry, hashes
├── ingestion/         # Crawling, cleaning, change detection, extraction
├── agents/            # Orchestrator, clarification, database, RAG agents
├── retrieval/         # Keyword, vector, hybrid retrieval, ranking logic
├── database/          # SQLite schema, models, and query helpers
├── models/            # Embedding / LLM provider abstractions
├── services/          # Shared business logic (source registry, validation, etc.)
├── api/               # FastAPI backend
├── ui/                # Streamlit frontend
├── scripts/           # One-off / maintenance scripts (e.g., manual ingestion runs)
├── logs/              # Structured application and ingestion logs
└── tests/
    ├── unit/          # Unit tests
    ├── integration/   # Integration tests across modules
    └── evaluation/    # Retrieval and answer-quality evaluation scripts
```

**Note:** Generated data, SQLite databases, FAISS indexes, raw downloaded webpages, log files, caches, and secrets (`.env`) are expected to be excluded from Git via `.gitignore`.

---

## Planned Technology Stack

> Proposed stack — subject to change as the project evolves. Nothing below implies a completed integration.

- **Python** — primary language
- **FastAPI** — backend API layer
- **Streamlit** — initial UI layer
- **SQLite** — structured scheme storage (local-first, personal project)
- **FAISS** — local vector store
- **BeautifulSoup** — HTML parsing
- **Requests / an appropriate webpage loader** — content fetching
- **Embedding model** — configurable via environment settings (provider not fixed)
- **LLM provider** — configurable via environment settings (provider not fixed)
- **Pytest** — testing framework
- **Structured logging** — for ingestion and application observability

The architecture is intentionally **not locked to a single commercial LLM or embedding provider**.

---

## Configuration Approach

Configuration is planned to be handled through environment variables (see `.env.example`), including:

- LLM provider and model name
- Embedding provider and model name
- Database and vector store paths
- Source registry location
- Logging level

TODO: Finalize and document exact environment variable names once implemented.

---

## Local Setup Instructions (TODO)

> These steps describe the intended setup flow. Some details are placeholders until implementation is complete.

1. Clone the repository:
   ```bash
   git clone TODO-github-repo-url
   cd AgriSubsidyAI-RAG
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and fill in configuration values:
   ```bash
   cp .env.example .env
   ```
5. TODO: Document initial ingestion command once the ingestion pipeline is implemented.
6. TODO: Document how to run the FastAPI backend.
7. TODO: Document how to run the Streamlit UI.

---

## Example Questions

- "Which agricultural subsidy schemes may apply to me?"
- "Are there any irrigation subsidies for small farmers in Karnataka?"
- "What documents are required for a particular scheme?"
- "How can I apply for the scheme?"
- "Explain this subsidy in simple language."
- "Compare two agricultural schemes."
- "Answer in my preferred language."

If key details are missing, the system is designed to ask about:

- State
- District
- Farming activity
- Landholding size
- Farmer category
- Type of support required

---

## Expected Response Format (Planned)

A typical response is intended to include:

- A plain-language explanation of the relevant scheme(s)
- Source citations (URL, publisher type, date last checked)
- A note on data freshness
- A disclosure of conflicting information, if any exists
- A clear grounding statement, for example:

> "Based on the cited information, you may meet some of the listed conditions. Final eligibility and approval must be confirmed through the responsible government department."

---

## No-Hallucination and Safety Principles

- Answers must be **grounded in retrieved evidence** — not model assumptions.
- Every scheme recommendation should include **source references**.
- The system **must not guarantee eligibility**.
- **Missing information should trigger clarification questions**, not guesses.
- **Conflicting sources must be disclosed**, not silently resolved.
- **Official sources are prioritized** over secondary sources.
- **Secondary sources are clearly labeled** as such.
- **Missing database fields must never be generated or inferred by the LLM** — they remain `null`/`unknown`.
- The system should explicitly say when reliable information is unavailable.
- **Final approval always remains with the responsible government authority.**
- AgriSubsidyAI is an **educational assistant**, not an official government service.

---

## Testing and Evaluation Strategy (Planned)

No evaluation has been run yet. The planned evaluation strategy covers:

- Router decision accuracy (correct route selected for a given question)
- Retrieval relevance (structured and vector search)
- Citation correctness (citations match retrieved evidence)
- Answer faithfulness (no unsupported claims)
- Missing-information detection (clarification triggered appropriately)
- Conflicting-source handling (disclosure behavior)
- Multilingual query quality (once languages are tested)
- Database extraction validation (structured field accuracy)
- Website-change detection accuracy
- End-to-end integration tests across the full pipeline

TODO: Publish evaluation methodology and results once testing begins. No results exist today.

---

## Development Roadmap

### Phase 1 — Foundations
- [ ] Repository foundation
- [ ] Configuration system
- [ ] Source registry
- [ ] Structured logging setup
- [ ] Basic webpage ingestion

### Phase 2 — Knowledge Pipeline
- [ ] Content cleaning
- [ ] Metadata extraction
- [ ] Chunking strategy
- [ ] Embedding generation
- [ ] FAISS vector index
- [ ] Source citation tracking

### Phase 3 — Structured Data
- [ ] SQLite schema design
- [ ] Structured scheme extraction
- [ ] Validation workflow
- [ ] Database retrieval logic

### Phase 4 — Orchestration
- [ ] Orchestrator core logic
- [ ] Language and intent analysis
- [ ] Clarification logic
- [ ] Database route
- [ ] Knowledge route
- [ ] Hybrid route

### Phase 5 — Application Layer
- [ ] Streamlit interface
- [ ] FastAPI backend
- [ ] Conversation context handling
- [ ] Multilingual testing

### Phase 6 — Evaluation and Polish
- [ ] Retrieval evaluation
- [ ] Answer-grounding tests
- [ ] Source freshness monitoring
- [ ] Error handling
- [ ] Documentation and screenshots

---

## Known Limitations

- The project is in an early architecture and development stage; most components are not yet built.
- No performance, accuracy, or coverage statistics exist yet.
- No languages have been tested for multilingual support.
- Secondary-source information may be incomplete, outdated, or inaccurate.
- Change detection confirms content changes but cannot verify factual correctness of source content.
- No government partnership, endorsement, or data-sharing agreement exists.

---

## Responsible-Use Disclaimer

AgriSubsidyAI is an **educational, portfolio-oriented project**. It is not a substitute for official government guidance. Users should always:

- Verify scheme details directly with the relevant government department
- Treat AI-generated explanations as a **starting point**, not a final answer
- Understand that eligibility, deadlines, and application procedures can change without notice

---

## Contributing

This is currently a personal learning project. Contribution guidelines will be added as the architecture stabilizes.

TODO: Add contribution guidelines, coding standards, and issue/PR templates once the repository is public.

---

## License

TODO: Add chosen license (e.g., MIT, Apache 2.0) and include the corresponding `LICENSE` file.

---

## Project Links and Assets (TODO)

- GitHub repository: TODO
- Application screenshot: TODO
- Architecture image: TODO
- Demo URL: TODO
- Tested languages: TODO
- Final LLM provider: TODO
- Final embedding model: TODO
- Contact information: TODO
