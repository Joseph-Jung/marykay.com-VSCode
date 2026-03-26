# Search Agent — Implementation Plan

## Overview

Build a consumer-facing search website powered by the scraped MaryKay
corpus (`3.Result/documents.jsonl` — 298 records, 149 EN + 149 ES).
The site provides hybrid search (keyword + semantic) with rich product
display including images, descriptions, FAQ answers, and cited sources.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Browser (Consumer)                │
│  ┌──────────────────────────────────────────────┐   │
│  │  Search Bar  │  Filters  │  Locale Toggle    │   │
│  ├──────────────────────────────────────────────┤   │
│  │  Results Grid: Product Cards with Images     │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐        │   │
│  │  │  Image  │ │  Image  │ │  Image  │        │   │
│  │  │  Name   │ │  Name   │ │  Name   │        │   │
│  │  │  Price  │ │  Price  │ │  Price  │        │   │
│  │  │  Desc   │ │  Desc   │ │  Desc   │        │   │
│  │  └─────────┘ └─────────┘ └─────────┘        │   │
│  ├──────────────────────────────────────────────┤   │
│  │  Product Detail Panel (expandable)           │   │
│  │  Full description, benefits, how-to, FAQ     │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────┬──────────────────────────────────┘
                   │ HTTP API
┌──────────────────▼──────────────────────────────────┐
│                  Backend (Python)                     │
│  ┌────────────┐  ┌────────────┐  ┌───────────────┐  │
│  │ FastAPI     │  │ Search     │  │ Data Loader   │  │
│  │ Routes      │──│ Engine     │──│ documents.jsonl│  │
│  │ /api/search │  │ BM25 +     │  │ → Index       │  │
│  │ /api/product│  │ TF-IDF     │  │ → Chunks      │  │
│  └────────────┘  └────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Backend** | Python + FastAPI | Already have Python venv; async, fast |
| **Search engine** | `rank_bm25` + `scikit-learn` TF-IDF | No external services needed; runs in-process |
| **Frontend** | Vanilla HTML/CSS/JS (single-page) | Zero build step; fast to iterate |
| **CSS framework** | Minimal custom CSS (grid layout) | Clean product card display |
| **Data source** | `documents.jsonl` loaded at startup | In-memory index for fast search |
| **Image display** | Direct links to marykay.com CDN | 146/149 EN pages have product images |

### Why NOT heavier tooling?

- No database needed — 298 records fits comfortably in memory
- No Node/React build chain — a single HTML file with fetch() is sufficient
- No vector embeddings required initially — BM25 + TF-IDF hybrid covers the corpus well at this scale
- Can add semantic embeddings later as an enhancement

---

## Phase 1: Data Preprocessing & Index

### 1.1 Load and Enrich Corpus

Read `documents.jsonl` and build search-optimized records:

```python
# Per record, build a "search_text" combining boosted fields:
search_text = (
    f"{title} {title} {title} "      # 3x boost
    f"{h1} {h1} "                     # 2x boost
    f"{product_name} {product_name} " # 2x boost
    f"{' '.join(headings)} "          # 1x
    f"{meta_description} "            # 1x
    f"{main_text}"                    # 1x
)
```

### 1.2 Chunking Strategy

Per the search-agent spec (300–800 tokens, 10–20% overlap):

- Split `main_text` into chunks of ~500 tokens with 75-token overlap
- Attach `canonical_url`, nearest heading, and record index to each chunk
- Build BM25 index over chunks for granular retrieval
- Build TF-IDF matrix over full records for page-level ranking

### 1.3 Product Image Extraction

From the corpus analysis:
- Product images use pattern: `demandware.static/-/Sites-us-master-catalog/` or contain `PRD`
- Filter out logos/icons (logo.svg, icon images)
- Store primary product image URL per record

**Output:** In-memory index ready at server startup.

---

## Phase 2: Backend API (FastAPI)

### 2.1 Project Structure

```
search-site/
├── app.py              # FastAPI application + search logic
├── static/
│   ├── index.html      # Single-page frontend
│   ├── style.css       # Product cards, grid, responsive
│   └── app.js          # Search interaction, rendering
└── data/
    └── documents.jsonl  # Symlink or copy from 3.Result/
```

### 2.2 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /` | GET | Serve the frontend HTML |
| `GET /api/search?q=...&locale=en&page=1` | GET | Hybrid search, returns ranked results |
| `GET /api/product/{content_hash}` | GET | Full product detail by content_hash |
| `GET /api/categories` | GET | List all categories for filter sidebar |
| `GET /api/faq?q=...` | GET | FAQ-specific search across faq_pairs |

### 2.3 Search Response Schema

```json
{
  "query": "moisturizer spf",
  "total_results": 12,
  "page": 1,
  "results": [
    {
      "content_hash": "abc123...",
      "title": "Mary Kay® CC Cream SPF 15",
      "h1": "Mary Kay® CC Cream Sunscreen Broad Spectrum SPF 15*",
      "product_name": "Mary Kay® CC Cream...",
      "price": "$22.00",
      "image_url": "https://www.marykay.com/dw/image/v2/...",
      "image_alt": "Tube of Mary Kay CC Cream...",
      "meta_description": "...",
      "category": "Makeup > Face > CC Cream",
      "url": "https://www.marykay.com/en/...",
      "canonical_url": "...",
      "snippet": "...highlighted matching text...",
      "score": 0.87,
      "locale": "en_US"
    }
  ],
  "facets": {
    "categories": [{"name": "Skincare", "count": 5}, ...],
    "locales": [{"name": "en_US", "count": 8}, ...]
  }
}
```

### 2.4 Search Algorithm (Hybrid)

```
1. Tokenize query → lowercase, remove stopwords
2. BM25 search over chunks → get top 50 chunk matches
3. TF-IDF search over full records → get top 50 record matches
4. Merge: map chunk hits back to parent records
5. Score = 0.6 * BM25_norm + 0.4 * TFIDF_norm
6. Apply locale filter if specified
7. Deduplicate by content_hash, keep highest score
8. Return top 20 with snippet extraction
```

---

## Phase 3: Frontend

### 3.1 Layout

```
┌──────────────────────────────────────────────────────────┐
│  🔍 [Search Mary Kay products...        ] [EN|ES] [🔎]  │
├──────────────┬───────────────────────────────────────────┤
│  Filters     │  Results                                  │
│              │                                           │
│  Category    │  ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  □ Skincare  │  │ [IMAGE]  │ │ [IMAGE]  │ │ [IMAGE]  │  │
│  □ Makeup    │  │ Name     │ │ Name     │ │ Name     │  │
│  □ Fragrance │  │ $22.00   │ │ $18.00   │ │ $30.00   │  │
│  □ Body/Sun  │  │ ⭐ 4.2   │ │ ⭐ 3.8   │ │ ⭐ 4.5   │  │
│  □ Men's     │  │ snippet  │ │ snippet  │ │ snippet  │  │
│  □ Gifts     │  └──────────┘ └──────────┘ └──────────┘  │
│              │                                           │
│  Page Type   │  ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  □ Products  │  │ [IMAGE]  │ │ [IMAGE]  │ │ [IMAGE]  │  │
│  □ Content   │  │  ...     │ │  ...     │ │  ...     │  │
│  □ FAQ       │  └──────────┘ └──────────┘ └──────────┘  │
│              │                                           │
│              │  [< 1  2  3 >] pagination                 │
├──────────────┴───────────────────────────────────────────┤
│  Product Detail (expanded on card click)                 │
│  ┌───────────────────────────────────────────────────┐   │
│  │  [LARGE IMAGE]  │  Product Name                   │   │
│  │                 │  Price                           │   │
│  │                 │  Size                            │   │
│  │                 │  Category > Breadcrumb           │   │
│  │                 │                                  │   │
│  │                 │  📝 Description                  │   │
│  │                 │  ✅ Key Benefits                  │   │
│  │                 │  📋 How to Use                   │   │
│  │                 │  ⚠️  Warnings                     │   │
│  │                 │  🧴 Ingredients                   │   │
│  ├─────────────────┴──────────────────────────────────┤   │
│  │  ❓ FAQ Section                                     │   │
│  │  Q: How do I apply this?                           │   │
│  │  A: Apply evenly to clean skin...                  │   │
│  ├────────────────────────────────────────────────────┤   │
│  │  🔗 Source: marykay.com/en/...  (canonical URL)    │   │
│  └────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### 3.2 Key UI Features

| Feature | Implementation |
|---------|---------------|
| **Instant search** | Debounced input (300ms) → fetch `/api/search` |
| **Product cards** | CSS Grid, 3 columns desktop / 2 tablet / 1 mobile |
| **Image display** | Product image from CDN with lazy loading + fallback placeholder |
| **Expandable detail** | Click card → slide-down panel with full product info |
| **FAQ accordion** | Collapsible Q&A pairs within detail panel |
| **Locale toggle** | EN / ES switch filters results by locale |
| **Category filters** | Checkbox sidebar, extracted from breadcrumbs |
| **Snippet highlighting** | Bold matched query terms in result snippets |
| **Pagination** | 12 results per page with page controls |
| **Responsive** | Mobile-first CSS, adapts to all screen sizes |
| **No-results state** | Friendly message with suggested searches |

### 3.3 Product Image Handling

```
Priority order for display:
1. First image with "PRD" or "hi-res" in src (product photo)
2. First image with meaningful alt text (not "logo")
3. Placeholder SVG with product name initials
```

Images link to marykay.com CDN directly — `?sw=400&sh=400&sm=fit` for
cards, `?sw=800&sh=800&sm=fit` for detail view.

---

## Phase 4: Search Quality & Rules

Per the search-agent spec:

| Rule | Implementation |
|------|----------------|
| **No hallucination** | All displayed content comes directly from corpus fields |
| **Cite all claims** | Every result shows `canonical_url` as source link |
| **Not found = say so** | "No results found for X. Try searching for..." message |
| **Prefer product detail** | Product pages get 1.2x score boost over category pages |
| **Confidence scoring** | high (>0.7), medium (0.4–0.7), low (<0.4) based on normalized search score |

### Answer Format (for API consumers)

The `/api/search` response includes per-result:
```json
{
  "answer": "extracted snippet",
  "confidence": "high",
  "citations": ["https://www.marykay.com/en/..."],
  "related": ["content_hash_1", "content_hash_2"]
}
```

---

## Phase 5: Testing & Polish

| Step | Action |
|------|--------|
| 5.1 | Test 20 representative queries (product names, categories, ingredients, concerns) |
| 5.2 | Verify all product images load correctly |
| 5.3 | Test EN/ES locale switching |
| 5.4 | Test mobile responsiveness |
| 5.5 | Verify "not found" handling |
| 5.6 | Performance check — search response < 200ms for 298-record corpus |

### Test Queries

1. "cc cream spf" → should find CC Cream product
2. "anti aging" → skincare concern pages
3. "lipstick shades" → lip product pages
4. "men skincare" → MKMen products
5. "gift under 25" → gift price range pages
6. "ingredientes" (ES) → Spanish ingredient pages
7. "how to apply foundation" → content/tutorial pages
8. "acne treatment" → Clear Proof collection
9. "fragrance floral" → fragrance category
10. "moisturizer for dry skin" → skincare concern pages

---

## Deliverables

```
search-site/
├── app.py                  # FastAPI backend with search engine
├── static/
│   ├── index.html          # Consumer-facing search page
│   ├── style.css           # Responsive product grid styles
│   └── app.js              # Search interaction logic
├── data/
│   └── documents.jsonl     # Corpus data file
├── requirements.txt        # Python dependencies
└── README.md               # Setup & run instructions
```

**To run:** `pip install -r requirements.txt && python app.py`
**Access:** `http://localhost:8000`

---

## Execution Order

```
Phase 1  →  Data preprocessing & index building (in app.py startup)
Phase 2  →  Backend API endpoints
Phase 3  →  Frontend HTML/CSS/JS
Phase 4  →  Search quality tuning & rules
Phase 5  →  Testing & polish
```

Estimated file count: **5 files** (app.py, index.html, style.css, app.js, requirements.txt)

---

## Future Enhancements (out of scope for v1)

1. **Semantic embeddings** — Add sentence-transformer embeddings for better "meaning" search
2. **Autocomplete** — Suggest products/categories as user types
3. **Image proxy** — Cache product images locally to avoid CDN dependency
4. **Analytics** — Track popular queries and zero-result queries
5. **AI answer synthesis** — Use LLM to synthesize natural-language answers from retrieved chunks (full RAG)
