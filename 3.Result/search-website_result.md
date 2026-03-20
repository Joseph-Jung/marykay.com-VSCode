# Search Website — Result Report

**Date:** 2026-02-25
**Status:** COMPLETE — 18/18 tests passed

---

## Executive Summary

Built a consumer-facing search website for the Mary Kay product corpus
(298 records). The site provides hybrid BM25 + TF-IDF search with
product image display, expandable detail panels, FAQ sections, category
filters, and EN/ES locale switching. All served from a single Python
process with no external dependencies.

---

## How to Run

```bash
cd search-site
source ../scraper/.venv/bin/activate
pip install -r requirements.txt
python app.py
# Open http://localhost:8000
```

---

## Architecture

```
Browser (localhost:8000)
  │
  ├── GET /                  → index.html (SPA)
  ├── GET /static/*          → style.css, app.js
  ├── GET /api/search?q=...  → Hybrid search results (JSON)
  ├── GET /api/product/{id}  → Full product detail (JSON)
  ├── GET /api/categories    → Category facets (JSON)
  └── GET /api/faq?q=...     → FAQ-specific search (JSON)
  │
FastAPI + BM25 + TF-IDF (in-memory, 298 records)
  │
documents.jsonl (5 MB corpus)
```

---

## Files Delivered

```
search-site/
├── app.py              349 lines — Backend: FastAPI, search engine, API endpoints
├── static/
│   ├── index.html       56 lines — Single-page HTML shell
│   ├── style.css       434 lines — Responsive product grid, cards, detail panel
│   └── app.js          312 lines — Search interaction, rendering, detail views
├── data/
│   └── documents.jsonl  symlink → 3.Result/documents.jsonl
└── requirements.txt     4 deps — fastapi, uvicorn, rank_bm25, scikit-learn
```

**Total: 5 files, ~1,150 lines of code**

---

## Features Implemented

### Search

| Feature | Details |
|---------|---------|
| Hybrid search | BM25 (60%) + TF-IDF (40%) with product page 1.2x boost |
| Field boosting | title 3x, h1 2x, product_name 2x, headings 1x, main_text 1x |
| Instant search | 300ms debounce on keystroke |
| Snippet extraction | Context-aware snippets with query term highlighting |
| Confidence scoring | high (>0.7), medium (0.4-0.7), low (<0.4) per result |
| No hallucination | All content sourced directly from corpus — no generation |
| Citation | Every result links to canonical marykay.com URL |

### Product Display

| Feature | Details |
|---------|---------|
| Product images | CDN images with size adaptation (400px cards, 800px detail) |
| Image coverage | 146/149 EN pages have product images |
| Image fallback | Placeholder icon when no product image available |
| Price display | Extracted from page text ($X.XX pattern) |
| Product cards | 3-column responsive grid (2 on tablet, 1 on mobile) |

### Detail Panel

| Feature | Details |
|---------|---------|
| Expandable overlay | Click any card to view full details |
| Sections | Description, Key Benefits, How to Use, Ingredients, Warnings |
| FAQ accordion | Collapsible Q&A pairs from corpus |
| Source link | Direct link to marykay.com product page |
| Breadcrumbs | Category path displayed at top |

### Filtering

| Feature | Details |
|---------|---------|
| Locale toggle | EN / ES switch in header |
| Category filter | Radio buttons in sidebar with counts |
| Page type filter | Product / Category / Content |
| Faceted counts | Dynamic counts update with each search |
| Clear filters | One-click clear for each filter group |

### UI/UX

| Feature | Details |
|---------|---------|
| Responsive | Mobile-first CSS, adapts 480px → 768px → 1024px+ |
| Pink theme | Mary Kay brand-aligned color palette |
| Loading states | Spinner during search, opacity fade on results |
| Empty states | Friendly "no results" message with suggestions |
| Keyboard | Enter to search, Escape to close detail panel |
| Pagination | Numbered pages, 12 results per page |

---

## Test Results (18/18 Passed)

### Search Query Tests (10/10)

| # | Query | Locale | Results | Top Score | Top Result | Status |
|---|-------|--------|---------|-----------|------------|--------|
| 1 | cc cream spf | en_US | 58 | 0.989 | CC Cream SPF 15 | PASS |
| 2 | anti aging | en_US | 5 | 1.000 | Ingredient Glossary | PASS |
| 3 | lipstick | en_US | 13 | 1.063 | Gel Semi-Shine Lipstick | PASS |
| 4 | men skincare | en_US | 35 | 1.000 | Men's Skincare | PASS |
| 5 | gift under 25 | en_US | 132 | 1.199 | Gift Bag | PASS |
| 6 | ingredientes | es_US | 12 | 0.964 | Spanish results | PASS |
| 7 | foundation | en_US | 25 | 0.982 | Foundation page | PASS |
| 8 | acne | en_US | 30 | 1.013 | Clear Proof Cleansing Gel | PASS |
| 9 | fragrance floral | en_US | 26 | 1.000 | Floral Fragrance | PASS |
| 10 | moisturizer dry skin | en_US | 77 | 1.195 | Hydrating Regimen | PASS |

### Product Detail Tests (6/6)

| Check | Status |
|-------|--------|
| has title | PASS |
| has h1 | PASS |
| has image | PASS |
| has main_text (>100 chars) | PASS |
| has faq_pairs | PASS |
| has price | PASS |

### Endpoint Tests (2/2)

| Endpoint | Check | Status |
|----------|-------|--------|
| /api/categories | >3 categories found (41) | PASS |
| /api/faq?q=how | >0 FAQ results (24) | PASS |

### Frontend Asset Tests (3/3)

| Asset | HTTP Status |
|-------|-------------|
| / (index.html) | 200 |
| /static/style.css | 200 |
| /static/app.js | 200 |

---

## Performance

| Metric | Value |
|--------|-------|
| Index build time | ~2 seconds (298 records) |
| Search response time | <50ms (in-memory BM25 + TF-IDF) |
| Memory usage | ~80 MB (corpus + indices) |
| Startup time | ~3 seconds total |

---

## Known Limitations

1. **No semantic embeddings** — BM25 + TF-IDF handles exact/fuzzy keyword matching well but misses purely conceptual queries (e.g., "something for wrinkles" won't match "age-fighting" unless keywords overlap).
2. **Prices from text extraction** — Prices parsed via regex from main_text; some may be inaccurate for multi-variant products.
3. **Image hotlinking** — Product images load directly from marykay.com CDN. If their CDN blocks cross-origin requests or changes URLs, images will break.
4. **No persistent state** — Search index rebuilds on every server restart (takes ~2s, acceptable at this scale).

---

## Future Enhancements

1. **Semantic search** — Add sentence-transformer embeddings for meaning-based retrieval
2. **Autocomplete** — Suggest products/categories as user types
3. **Image caching** — Proxy and cache product images locally
4. **AI answer synthesis** — LLM-generated natural language answers from retrieved chunks (full RAG)
5. **Analytics dashboard** — Track popular queries, zero-result queries, click-through rates
