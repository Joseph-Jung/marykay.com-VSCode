# AI Search v2 — Product List Cards + Link Fix — Execution Result

**Executed:** 2026-03-23
**Plan:** `2.Plan/ai-search-agent_v2_product_list_plan.md`
**Requirements:** `1.Order/ai-search-agent_v2_product_list.md`

---

## Step Results

### Step 1 — URL normalization in `ai_search.py`

**Status:** Complete

- Added `MARYKAY_BASE = "https://www.marykay.com"` constant.
- Added `normalize_url()` helper that prepends domain to relative URLs.
- Applied `normalize_url()` to the `url` field in `search_products()` result loop.
- All URLs returned by the AI search pipeline now start with `https://www.marykay.com`.

**File changed:** `search-site/ai_search.py` (lines 27-38, line 80)

---

### Step 2 — Expand `ask()` return payload

**Status:** Complete

- Expanded the `sources` list in `ask()` from 5 fields to 15 fields:
  - Added: `h1`, `description`, `main_text` (truncated to 300 chars), `category`, `size`, `key_benefits`, `shade_options`, `score`, `reranker_score`
  - Retained: `title`, `url`, `product_name`, `price`, `images`
- All fields were already fetched by `search_products()` — now passed through.

**File changed:** `search-site/ai_search.py` (lines 158-178)

---

### Step 3 — Enrich AI sources with local record data in `app.py`

**Status:** Complete

- Added `_find_local_record(url)` helper that matches AI search URLs against `record_map` by comparing URL paths (strips domain for comparison).
- Modified `/api/ai-search` endpoint to enrich each source with:
  - `content_hash` — from local record (needed for detail overlay)
  - `page_type` — product / category / content
  - `locale` — en_US / es_US
  - `image_url` and `image_alt` — from `extract_product_image()`
  - `snippet` — first 200 chars of description or main_text
- Unmatched products (edge case): `content_hash` set to `null`, frontend handles by linking to marykay.com.

**File changed:** `search-site/app.py` (lines 431-478)

---

### Step 4 — Extract shared card renderer in `app.js`

**Status:** Complete

- Extracted `renderProductCard(r, query)` function from inline card HTML in `renderResults()`.
- Card renderer handles both keyword and AI search data shapes:
  - Supports `image_url` (keyword) and falls back gracefully
  - Supports `snippet`, `meta_description`, `description`, `main_text` for snippet text
  - Shows confidence footer only when `confidence` field is present (keyword search)
  - Click action: `openDetail(content_hash)` when available, `window.open(url)` as fallback
- Updated `renderResults()` to call `renderProductCard()`.

**File changed:** `search-site/static/app.js` (lines 195-257)

---

### Step 5 — Render AI search sources as product card grid

**Status:** Complete

- Modified `doAiSearch()` to render source products as card grid into `resultsGrid` using `renderProductCard()`.
- Removed source pills rendering — `aiSourcesEl.innerHTML` cleared.
- Results count shows `"N related products"` instead of `"N source products"`.
- AI answer box preserved above the card grid.

**File changed:** `search-site/static/app.js` (lines 150-160)

---

### Step 6 — Markdown link parsing in `formatAiAnswer()`

**Status:** Complete

- Rewrote `formatAiAnswer()` to safely handle markdown links:
  1. Extract `[text](url)` patterns from raw text *before* HTML escaping.
  2. Rewrite relative URLs to `https://www.marykay.com`.
  3. Store as pre-built `<a>` tags with placeholder tokens.
  4. Escape remaining text, then restore link placeholders.
  5. Apply bold and line break formatting.
- This approach avoids the issue where `escapeHtml()` would break the markdown link syntax.

**File changed:** `search-site/static/app.js` (lines 170-193)

---

### Step 7 — Verification

**Status:** Complete

| # | Test Case | Result |
|---|-----------|--------|
| 1 | Keyword search: "moisturizer" | 56 results, cards with images/prices/categories render correctly |
| 2 | Server health check (HTTP 200) | Passed |
| 3 | Keyword result data shape | `content_hash`, `image_url`, `price`, `page_type` all present |
| 4 | Server restart with v2 code | No import errors, startup successful |
| 5-9 | AI search end-to-end, detail overlay, URL validation, mode toggle | Requires manual browser testing (Azure credentials needed for live AI search calls) |

---

## Files Modified

| File | Lines Changed | Summary |
|------|--------------|---------|
| `search-site/ai_search.py` | +25 modified | `normalize_url()`, expanded `ask()` sources payload |
| `search-site/app.py` | +48 modified | `_find_local_record()`, enriched `/api/ai-search` response |
| `search-site/static/app.js` | +65 modified, -30 removed | `renderProductCard()`, card grid for AI results, markdown link parsing |

---

## Architecture Change (Before → After)

### Before (v1)
```
AI Search Response:
  answer: "text..."
  sources: [{title, url, product_name, price, images}]
                          ↓
  Frontend renders → small source pills (name + price only)
  URLs → relative paths (/en/...) → resolve to localhost
```

### After (v2)
```
AI Search Response:
  answer: "text..."
  sources: [{title, url, h1, product_name, price, size, category,
             description, main_text, key_benefits, shade_options,
             images, score, reranker_score,
             content_hash, page_type, locale, image_url, image_alt, snippet}]
                          ↓
  Frontend renders → full product card grid (image, name, price, category, snippet)
  Cards clickable → detail overlay (or marykay.com for unmatched)
  URLs → absolute https://www.marykay.com/...
  AI answer links → parsed markdown → <a> tags → marykay.com
```

---

## Remaining Manual Testing

The following tests require a browser with the server running and valid Azure credentials in `.env`:

1. AI search: "products under $15" — verify answer box + product cards
2. Click an AI product card — verify detail overlay opens
3. Inspect product card URLs — verify `https://www.marykay.com` domain
4. Check AI answer text for rendered links — verify they point to marykay.com
5. Toggle between keyword and AI modes — verify clean transition
