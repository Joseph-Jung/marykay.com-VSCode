# AI Search Agent v2 — Product List Cards + Link Fix

## Overview

Enhance the AI Search experience so that, in addition to the AI-generated answer, the **source products are displayed as product cards** identical to the keyword search results grid. Currently, AI search only shows small source pills below the answer. Users should see the same rich product card layout (image, name, price, category, snippet) they get from keyword search.

Additionally, **all product links in AI search results must point to `marykay.com`** (the live site), not the local search application.

---

## Current Behavior (v1)

```
┌─────────────────────────────────────────────────┐
│  AI Answer Box                                  │
│  "You can find Mary Kay gifts priced at $15..." │
│                                                 │
│  Sources                                        │
│  [Product A] [Product B] [Product C]  ← pills   │
└─────────────────────────────────────────────────┘
```

**Problems:**

1. Source products are shown as small clickable pills (name only + optional price) — no images, no category, no description.
2. Product links use relative URLs (e.g., `/en/best-sellers/...`) which resolve to the local search site (`localhost:8000`) instead of `https://www.marykay.com`.
3. No way to click into a product detail overlay from AI search results.

---

## Required Behavior (v2)

```
┌─────────────────────────────────────────────────┐
│  AI Answer Box                                  │
│  "You can find Mary Kay gifts priced at $15..." │
│  (links inside answer → marykay.com)            │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  "5 related products"                           │
│                                                 │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐        │
│  │ img  │  │ img  │  │ img  │  │ img  │        │
│  │ name │  │ name │  │ name │  │ name │        │
│  │ $22  │  │ $15  │  │ $18  │  │ $12  │        │
│  │ snip │  │ snip │  │ snip │  │ snip │        │
│  └──────┘  └──────┘  └──────┘  └──────┘        │
│                                                 │
│  (same card style as keyword search results)    │
└─────────────────────────────────────────────────┘
```

---

## Requirements

### R1 — Product Card Grid for AI Search Results

- After displaying the AI answer box, render the source products as **product cards** using the same card component/layout as keyword search (`renderResults` in `app.js`).
- Each card must display:
  - Product image (from `images` array, with Demandware resize)
  - Product name (or title as fallback)
  - Price
  - Category
  - Description snippet (first ~150 chars of `description` or `main_text`)
  - Badge indicating page type (product / category / content)
- Cards must be clickable to open the **product detail overlay** (same as keyword search), so users can view full product info, benefits, ingredients, FAQ, etc.

### R2 — Backend: Return Full Product Data for AI Sources

- The `/api/ai-search` endpoint must return enough data per source product to render a full product card:
  - `content_hash` — needed for the detail overlay lookup
  - `title`, `h1`, `url`, `canonical_url`
  - `product_name`, `price`, `size`, `category`
  - `description` (or `meta_description`)
  - `main_text` (first 300 chars for snippet)
  - `key_benefits`
  - `images` (array of image objects with `src` and `alt`)
  - `page_type` (product / category / content)
  - `locale`
  - `score` and/or `reranker_score`

- To obtain `content_hash` and local product fields not stored in Azure, cross-reference AI search results against the local `record_map` (match by URL or title).

### R3 — Fix Product URLs to Point to marykay.com

- All product URLs returned by AI search must use the full `https://www.marykay.com` domain.
- **Backend fix**: In `ai_search.py`, when building the source list, prepend `https://www.marykay.com` to any relative URL (URLs starting with `/`).
- **Frontend fix**: In `app.js`, ensure that product card links and AI answer links open `marykay.com` URLs, not local routes.
- The AI answer text itself may contain markdown links like `[Product Name](url)` — these URLs must also be rewritten to use the `marykay.com` domain.

### R4 — Preserve AI Answer Box Above Product Grid

- The AI answer box remains at the top, styled as it is now.
- Remove the current source pills section (`ai-sources`) — the product cards replace them.
- Show a count label: e.g., `"5 related products"` between the answer box and the product grid.

### R5 — Detail Overlay from AI Product Cards

- Clicking an AI search product card must open the same product detail overlay used by keyword search.
- This requires the `content_hash` to be available for each AI result so the `/api/product/{content_hash}` endpoint can be called.
- If a product from Azure AI Search cannot be matched to a local record (edge case), the card should link directly to `marykay.com` instead of opening the overlay.

---

## Implementation Plan

### Backend Changes (`ai_search.py` + `app.py`)

1. **`ai_search.py` — `search_products()`**: Already returns `title`, `url`, `product_name`, `price`, `category`, `images`, etc. Add `description` and `main_text` to the `select` list if not already included.

2. **`app.py` — `/api/ai-search` endpoint**: After calling `ai_search_ask()`, cross-reference each source product against the local `record_map` to enrich with:
   - `content_hash`
   - `page_type`
   - `locale`
   - `image` object (with `src` and `alt`)
   - Any missing fields

3. **URL rewriting**: In `ai_search.py`, normalize all `url` fields:
   ```python
   MARYKAY_BASE = "https://www.marykay.com"

   def normalize_url(url: str) -> str:
       if url and url.startswith("/"):
           return MARYKAY_BASE + url
       if url and not url.startswith("http"):
           return MARYKAY_BASE + "/" + url
       return url
   ```

### Frontend Changes (`app.js`)

1. **`doAiSearch()`**: After receiving the response, render product cards using the same `renderResults()` function (or a shared card-rendering helper) into `resultsGrid`.

2. **Remove source pills**: Remove the `aiSourcesEl` rendering block. The product cards replace it.

3. **AI answer link rewriting**: In `formatAiAnswer()`, convert markdown-style links `[text](url)` to HTML anchors with `marykay.com` URLs:
   ```javascript
   // Convert [text](url) to <a> tags with marykay.com domain
   html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, url) => {
     const fullUrl = url.startsWith("/") ? "https://www.marykay.com" + url : url;
     return `<a href="${fullUrl}" target="_blank" rel="noopener">${text}</a>`;
   });
   ```

4. **Shared card renderer**: Extract the card HTML template from `renderResults()` into a reusable function `renderProductCard(product)` that both keyword and AI search can call.

---

## Response Format (v2)

```json
{
  "answer": "For lightweight coverage with SPF protection, the **Mary Kay CC Cream** ($22.00) is an excellent choice...",
  "sources": [
    {
      "content_hash": "abc123...",
      "title": "Mary Kay® CC Cream Sunscreen Broad Spectrum SPF 15*",
      "url": "https://www.marykay.com/en/best-sellers/mary-kay-cc-cream-...",
      "product_name": "Mary Kay® CC Cream Sunscreen Broad Spectrum SPF 15*",
      "price": "$22.00",
      "category": "Best Sellers",
      "description": "This lightweight cream delivers 8 benefits in 1...",
      "main_text": "Mary Kay CC Cream provides lightweight coverage...",
      "images": [{"src": "https://media.marykay.com/...", "alt": "CC Cream"}],
      "page_type": "product",
      "locale": "en_US",
      "key_benefits": ["Lightweight coverage", "SPF 15 protection"],
      "score": 0.85,
      "reranker_score": 3.2
    }
  ]
}
```

---

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | AI search displays source products as card grid (image, name, price, category, snippet) identical to keyword search layout |
| 2 | Clicking a product card opens the detail overlay with full product info |
| 3 | All product URLs (in cards, answer text, and detail overlay) point to `https://www.marykay.com`, not the local site |
| 4 | AI answer box is preserved above the product card grid |
| 5 | Source pills section is removed (replaced by product cards) |
| 6 | Markdown links in AI answer text are rendered as clickable `<a>` tags pointing to marykay.com |
| 7 | Products that cannot be matched to a local record still render as cards with a direct link to marykay.com |
| 8 | No regression to keyword search functionality |

---

## Files to Modify

| File | Changes |
|------|---------|
| `search-site/ai_search.py` | Add URL normalization; include `description`/`main_text` in select fields |
| `search-site/app.py` | Enrich AI sources with `content_hash`, `page_type`, `locale`, `image` from local records |
| `search-site/static/app.js` | Render AI sources as product cards; add markdown link parsing; extract shared card renderer |
| `search-site/static/style.css` | Minor adjustments if needed for AI answer + card grid spacing |
| `search-site/static/index.html` | No changes expected (grid container already exists) |
