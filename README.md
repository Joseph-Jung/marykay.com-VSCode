# Mary Kay Product Search Engine

A full-stack search application for discovering Mary Kay products through **hybrid keyword search** (BM25 + TF-IDF) and **AI-powered natural language search** (Azure AI Search + GPT-4.1 RAG). The system crawls marykay.com, extracts structured product data, builds searchable indices, and serves results through a responsive web interface.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (Single-Page App)                │
│         Vanilla JS  ·  CSS Grid  ·  Fetch API              │
│  ┌──────────────────┐      ┌──────────────────────┐        │
│  │  Keyword Search   │      │     AI Search         │        │
│  │  (instant, local) │      │  (natural language)   │        │
│  └────────┬─────────┘      └──────────┬───────────┘        │
└───────────┼────────────────────────────┼────────────────────┘
            │ HTTP/JSON                  │ HTTP/JSON
┌───────────▼────────────────────────────▼────────────────────┐
│               FastAPI Backend (Python)                       │
│                                                              │
│  /api/search ──────► BM25 + TF-IDF Hybrid Engine            │
│  /api/ai-search ───► Azure AI Search + GPT-4.1 RAG          │
│  /api/product/{id} ► Product Detail Lookup                   │
│  /api/categories ──► Faceted Category Navigation             │
│  /api/faq ─────────► FAQ-Specific Search                     │
└───────┬──────────────────────────────────┬──────────────────┘
        │                                  │
┌───────▼───────────┐        ┌─────────────▼──────────────────┐
│   Local Indices    │        │       Azure Cloud Services     │
│                    │        │                                │
│ • documents.jsonl  │        │ • Azure AI Search              │
│   (298 records)    │        │   (marykay-products index)     │
│ • BM25 corpus      │        │ • text-embedding-3-large       │
│ • TF-IDF matrix    │        │   (3072-dim vectors)           │
│                    │        │ • GPT-4.1 (RAG answers)        │
│ In-memory, <50ms   │        │ ~2-3s latency                  │
└────────────────────┘        └────────────────────────────────┘
```

---

## Data Pipeline Flow

```
 ┌──────────────┐     ┌────────────────────┐     ┌──────────────────────┐
 │  1. SCRAPE    │────►│  2. LOCAL INDEX     │────►│  3. AZURE INDEX      │
 │              │     │                    │     │                      │
 │ Crawl 700+  │     │ Build BM25 + TF-IDF│     │ Create Azure Search  │
 │ URLs from    │     │ indices in memory   │     │ index, embed docs,   │
 │ marykay.com  │     │ on server start     │     │ upload to cloud      │
 │              │     │                    │     │                      │
 │ Output:      │     │ Serves keyword      │     │ Serves AI-powered    │
 │ documents.   │     │ search queries      │     │ natural language     │
 │ jsonl        │     │                    │     │ search queries       │
 └──────────────┘     └────────────────────┘     └──────────────────────┘
```

### Search Query Paths

**Keyword Search:**
```
User query → /api/search → BM25 (60%) + TF-IDF (40%) hybrid scoring
  → field boosting (title 3x, h1 2x, product_name 2x)
  → product page boost (1.2x)
  → faceted filtering → 12 results/page
```

**AI Search:**
```
User query → /api/ai-search → Azure AI Search (keyword + vector + semantic reranking)
  → top-5 products retrieved as context
  → GPT-4.1 generates grounded answer with citations
  → returns natural language answer + source product links
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Vanilla JavaScript, CSS Grid/Flexbox, Fetch API |
| **Backend** | Python 3.14, FastAPI, Uvicorn/Gunicorn |
| **Keyword Search** | rank_bm25, scikit-learn (TF-IDF) |
| **AI Search** | Azure AI Search, Azure OpenAI (GPT-4.1, text-embedding-3-large) |
| **Scraper** | BeautifulSoup4, httpx, lxml |
| **Infrastructure** | Azure App Service, Azure AI Search, Azure OpenAI |

---

## Project Structure

```
marykay.com-VSCode/
├── search-site/               # Main application
│   ├── app.py                 # FastAPI backend (search APIs, routing)
│   ├── ai_search.py           # Azure AI Search + GPT-4.1 RAG module
│   ├── requirements.txt       # Python dependencies
│   ├── startup.txt            # Production startup command
│   ├── .deployment            # Azure App Service deployment config
│   ├── data/
│   │   └── documents.jsonl    # Product corpus (298 records, 5 MB)
│   └── static/
│       ├── index.html         # Single-page app
│       ├── app.js             # Frontend search logic
│       └── style.css          # Responsive styling
├── scraper/
│   └── scraper.py             # Web crawler for marykay.com
├── scripts/
│   ├── create_index.py        # Create Azure AI Search index
│   ├── ingest_data.py         # Embed & upload documents to Azure
│   └── validate_index.py      # Validate Azure index health
├── 1.Order/                   # Requirements & specifications
├── 2.Plan/                    # Planning documents
└── 3.Result/                  # Execution results & output files
```

---

## Setup & Configuration

### Prerequisites

- Python 3.10+
- Azure AI Search service
- Azure OpenAI service (GPT-4.1 + text-embedding-3-large deployed)

### Environment Variables

Create a `.env` file in `search-site/`:

```env
# Azure AI Search
AZURE_AI_SEARCH_ENDPOINT=https://<your-search-service>.search.windows.net
AZURE_AI_SEARCH_KEY=<your-search-admin-key>
AZURE_AI_SEARCH_INDEX=marykay-products

# Azure OpenAI - Chat Model
CHAT_MODEL_ENDPOINT=https://<your-openai-endpoint>
CHAT_MODEL=gpt-4.1
API_KEY=<your-api-key>

# Azure OpenAI - Embedding Model
EMBEDDING_MODEL_ENDPOINT=https://<your-openai-endpoint>
EMBEDDING_MODEL=text-embedding-3-large

# Microsoft Foundry (optional)
AIPROJECT_ENDPOINT=https://<your-foundry-endpoint>
```

### Install Dependencies

```bash
cd search-site
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Commands to Run Each Feature

### 1. Run the Web Scraper

Crawls marykay.com, extracts product data, and outputs `documents.jsonl`.

```bash
cd scraper
python scraper.py
```

Output: `documents.jsonl` containing structured records for each scraped page (title, description, product fields, images, FAQs, etc.).

---

### 2. Create the Azure AI Search Index

Sets up the search index schema in Azure with vector, semantic, and keyword configurations.

```bash
cd scripts
python create_index.py
```

This creates a `marykay-products` index with 16 fields including vector embeddings (3072 dimensions) and semantic search profiles.

---

### 3. Ingest Data into Azure AI Search

Transforms documents, generates embeddings via text-embedding-3-large, and uploads to the Azure Search index.

```bash
cd scripts
python ingest_data.py
```

This reads from `documents.jsonl`, computes vector embeddings for each document, and bulk-uploads them to the Azure index.

---

### 4. Validate the Azure Search Index

Runs health checks and sample queries against the Azure index to confirm data was ingested correctly.

```bash
cd scripts
python validate_index.py
```

---

### 5. Start the Search Application (Development)

Launches the FastAPI server with auto-reload. Builds local BM25 + TF-IDF indices on startup (~2 seconds).

```bash
cd search-site
python app.py
```

Open **http://localhost:8000** in your browser.

- **Keyword Search** tab: Instant hybrid search powered by local indices (no Azure required)
- **AI Search** tab: Natural language search powered by Azure AI Search + GPT-4.1 (requires Azure credentials)

---

### 6. Start the Search Application (Production)

Uses Gunicorn with Uvicorn workers for production deployment.

```bash
cd search-site
source .venv/bin/activate
gunicorn -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 app:app
```

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Hybrid Keyword Search** | BM25 (60%) + TF-IDF (40%) with field boosting and product-page scoring |
| **AI Natural Language Search** | Azure AI Search + GPT-4.1 RAG with grounded answers and citations |
| **Faceted Filtering** | Filter by category, page type, and locale (EN/ES) |
| **Product Detail View** | Expandable overlay with description, benefits, ingredients, how-to-use, FAQs |
| **Snippet Highlighting** | Query terms highlighted in search result snippets |
| **Confidence Scoring** | Results scored as high (>0.7), medium (0.4-0.7), or low (<0.4) |
| **Bilingual Support** | English and Spanish content with locale toggle |
| **Responsive Design** | Mobile-friendly layout with CSS Grid |
| **Debounced Search** | 300ms debounce for instant-feel keyword search |

---

## Integration Points

| Service | Purpose | Used By |
|---------|---------|---------|
| **Azure AI Search** | Hybrid retrieval (keyword + vector + semantic reranking) | `ai_search.py` |
| **Azure OpenAI (GPT-4.1)** | Generate grounded natural language answers from retrieved products | `ai_search.py` |
| **Azure OpenAI (text-embedding-3-large)** | Generate 3072-dim vector embeddings for documents | `scripts/ingest_data.py` |
| **marykay.com** | Source data (web scraping, product images via CDN) | `scraper/scraper.py` |

---

## Performance

| Metric | Value |
|--------|-------|
| Corpus size | 298 pages |
| Index build time | ~2 seconds |
| Keyword search latency | <50 ms |
| AI search latency | ~2-3 seconds |
| Memory usage | ~80 MB |
| Results per page | 12 |
