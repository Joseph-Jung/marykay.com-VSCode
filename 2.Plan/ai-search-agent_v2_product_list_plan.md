# AI Search v2 — Product List Cards + Link Fix — Execution Plan

## Goal

Upgrade the AI Search experience so source products render as **full product cards** (identical to keyword search) instead of small pills, and all product URLs point to **`https://www.marykay.com`** instead of the local site.

---

## Prerequisites

| Item | Status |
|------|--------|
| AI Search v1 deployed (Azure AI Search + GPT-4.1 RAG) | Ready |
| Local corpus loaded (`record_map` with 298 records) | Ready |
| Keyword search product cards working | Ready — will reuse |
| Requirements doc (`1.Order/ai-search-agent_v2_product_list.md`) | Ready |

---

## Execution Steps

### Step 1 — Add URL normalization helper to `ai_search.py`

**File:** `search-site/ai_search.py`
**Requirement:** R3

Add a `normalize_url()` function that prepends `https://www.marykay.com` to any relative URL. Apply it to every `url` field returned by `search_products()` and `ask()`.

```python
MARYKAY_BASE = "https://www.marykay.com"

def normalize_url(url: str) -> str:
    """Ensure URL is absolute with marykay.com domain."""
    if not url:
        return ""
    if url.startswith("/"):
        return MARYKAY_BASE + url
    if not url.startswith("http"):
        return MARYKAY_BASE + "/" + url
    return url
```

Apply `normalize_url()` to the `url` field inside `search_products()` result loop and inside `ask()` sources list.

**Verify:** Call `/api/ai-search` and confirm all returned URLs start with `https://www.marykay.com`.

---

### Step 2 — Expand `ask()` return payload with full product data

**File:** `search-site/ai_search.py`
**Requirement:** R2

Currently `ask()` returns only `title`, `url`, `product_name`, `price`, `images` per source. Expand it to include all fields needed for product cards:

- `h1`, `description`, `main_text` (truncated to 300 chars for snippet)
- `category`, `size`
- `key_benefits`, `shade_options`
- `score`, `reranker_score`

These fields are already fetched by `search_products()` — they just need to be passed through in the `sources` list.

**Verify:** Call `/api/ai-search` and confirm each source contains the full field set.

---

### Step 3 — Enrich AI sources with local record data in `app.py`

**File:** `search-site/app.py`
**Requirement:** R2, R5

Modify the `/api/ai-search` endpoint to cross-reference each AI source against the local `record_map` and enrich with fields that only exist locally:

1. Build a URL-to-record lookup from `record_map` (match by URL path).
2. For each AI source, find the matching local record and add:
   - `content_hash` (required for detail overlay)
   - `page_type` (product / category / content)
   - `locale`
   - `image_url` and `image_alt` (from `extract_product_image()`)
   - `confidence` score label
3. If no local match is found, set `content_hash` to `null` (frontend will handle this by linking to marykay.com directly).

```python
@app.post("/api/ai-search")
async def api_ai_search(request: Request):
    body = await request.json()
    user_query = body.get("query", "").strip()
    if not user_query:
        return {"answer": "Please enter a question.", "sources": []}

    result = ai_search_ask(user_query)

    # Enrich sources with local record data
    enriched_sources = []
    for source in result.get("sources", []):
        local_rec = _find_local_record(source.get("url", ""))
        if local_rec:
            source["content_hash"] = local_rec["content_hash"]
            source["page_type"] = local_rec["_page_type"]
            source["locale"] = local_rec.get("locale", "")
            source["image_url"] = local_rec["_image"].get("src", "")
            source["image_alt"] = local_rec["_image"].get("alt", "")
            source["snippet"] = (source.get("description", "") or
                                 source.get("main_text", ""))[:200]
        else:
            source["content_hash"] = None
            source["page_type"] = "product"
            source["locale"] = ""
            source["image_url"] = ""
            source["image_alt"] = ""
            source["snippet"] = (source.get("description", "") or
                                 source.get("main_text", ""))[:200]
        enriched_sources.append(source)

    result["sources"] = enriched_sources
    return result
```

Add the helper function `_find_local_record()` that strips domain from URL and matches against `record_map` values by comparing URL paths.

**Verify:** Call `/api/ai-search` and confirm each source has `content_hash`, `page_type`, `locale`, `image_url`.

---

### Step 4 — Extract shared card renderer in `app.js`

**File:** `search-site/static/app.js`
**Requirement:** R1

Extract the product card HTML template from the existing `renderResults()` function into a standalone `renderProductCard(product)` function. Then call it from both `renderResults()` and the new AI search renderer.

```javascript
function renderProductCard(r, query) {
    const badgeClass = r.page_type === "product" ? "badge-product" :
                       r.page_type === "content" ? "badge-content" : "badge-category";

    const imgSrc = r.image_url || (r.images && r.images[0]) || "";
    const imgAlt = r.image_alt || r.product_name || r.title || "";
    const imageHtml = imgSrc
      ? `<img class="card-image" src="${resize(imgSrc, 400)}" alt="${escapeHtml(imgAlt)}" loading="lazy" onerror="this.parentElement.innerHTML='<div class=card-image-placeholder>&#x1f48e;</div>'">`
      : `<div class="card-image-placeholder">&#x1f48e;</div>`;

    const snippet = r.snippet || r.description || (r.main_text || "").substring(0, 200);
    const displaySnippet = query ? highlightTerms(snippet, query) : escapeHtml(snippet);
    const name = r.product_name || r.h1 || r.title;
    const clickAction = r.content_hash
      ? `onclick="openDetail('${r.content_hash}')"`
      : `onclick="window.open('${escapeHtml(r.url)}', '_blank')"`;

    return `
      <div class="product-card" ${clickAction}>
        <div class="card-image-wrap">
          ${imageHtml}
          <span class="card-badge ${badgeClass}">${r.page_type || "product"}</span>
        </div>
        <div class="card-body">
          <div class="card-category">${escapeHtml(r.category || "")}</div>
          <div class="card-title">${escapeHtml(name)}</div>
          ${r.price ? `<div class="card-price">${escapeHtml(r.price)}</div>` : ""}
          <div class="card-snippet">${displaySnippet}</div>
        </div>
      </div>`;
}
```

Update `renderResults()` to call `renderProductCard()` for each result instead of having inline card HTML.

**Verify:** Keyword search still renders cards exactly as before — no visual regression.

---

### Step 5 — Render AI search sources as product card grid

**File:** `search-site/static/app.js`
**Requirement:** R1, R4, R5

Modify `doAiSearch()` to:

1. Show the AI answer box (unchanged).
2. Remove the source pills rendering (`aiSourcesEl` block).
3. Set `resultsCount` to `"N related products"`.
4. Render source products into `resultsGrid` using `renderProductCard()`.

```javascript
// Inside doAiSearch(), after showing AI answer:
aiSourcesEl.innerHTML = "";  // Remove pills

if (data.sources && data.sources.length > 0) {
    resultsCount.innerHTML = `<strong>${data.sources.length}</strong> related products`;
    resultsGrid.innerHTML = data.sources.map(s =>
        renderProductCard(s, currentQuery)
    ).join("");
} else {
    resultsCount.innerHTML = "";
    resultsGrid.innerHTML = "";
}
```

Cards with `content_hash` open the detail overlay on click. Cards without `content_hash` (unmatched) open the marykay.com URL in a new tab.

**Verify:** Search "products under $15" in AI mode → see answer box + product cards below it with images, names, prices.

---

### Step 6 — Add markdown link parsing to `formatAiAnswer()`

**File:** `search-site/static/app.js`
**Requirement:** R3

Enhance `formatAiAnswer()` to:

1. Convert markdown links `[text](url)` to HTML `<a>` tags.
2. Rewrite any relative URLs in those links to `https://www.marykay.com`.

```javascript
function formatAiAnswer(text) {
    if (!text) return "";
    let html = escapeHtml(text);
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    // Markdown links [text](url) → <a> with marykay.com domain
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
        let fullUrl = url;
        if (url.startsWith("/")) fullUrl = "https://www.marykay.com" + url;
        else if (!url.startsWith("http")) fullUrl = "https://www.marykay.com/" + url;
        return `<a href="${fullUrl}" target="_blank" rel="noopener">${linkText}</a>`;
    });
    // Line breaks
    html = html.replace(/\n/g, "<br>");
    return html;
}
```

**Verify:** AI answer containing `[Product Name](/en/...)` renders as a clickable link to `https://www.marykay.com/en/...`.

---

### Step 7 — End-to-end testing and validation

**Executor:** Manual

Run the following test scenarios:

| # | Test Case | Expected Result |
|---|-----------|-----------------|
| 1 | AI search: "products under $15" | Answer box + product cards with images, prices, categories |
| 2 | Click a product card from AI results | Detail overlay opens with full product info |
| 3 | Check product URLs in AI results | All point to `https://www.marykay.com/...` |
| 4 | Check links inside AI answer text | Rendered as `<a>` tags pointing to marykay.com |
| 5 | AI search: "best moisturizer for dry skin" | Answer + related product cards |
| 6 | Keyword search: "moisturizer" | Product cards render as before (no regression) |
| 7 | Click product card from keyword search | Detail overlay works as before |
| 8 | AI search with no results | "No products found" message, no errors |
| 9 | Toggle between AI and keyword modes | Clean transition, no stale cards |

---

## Step Dependency Graph

```
Step 1  (URL normalization in ai_search.py)
  │
  ▼
Step 2  (Expand ask() return payload)
  │
  ▼
Step 3  (Enrich sources in app.py)          ← backend complete
  │
  ▼
Step 4  (Extract shared card renderer)
  │
  ▼
Step 5  (Render AI sources as cards)
  │
  ▼
Step 6  (Markdown link parsing)             ← frontend complete
  │
  ▼
Step 7  (End-to-end testing)
```

Steps 1 → 2 → 3 are sequential (each builds on the prior).
Steps 4 → 5 → 6 are sequential (each builds on the prior).
Steps 1-3 (backend) and Step 4 (card extraction) can run in parallel, but Step 5 depends on both Step 3 and Step 4.

---

## Files Modified (Summary)

| Step | File | Change |
|------|------|--------|
| 1 | `search-site/ai_search.py` | Add `normalize_url()`, apply to all returned URLs |
| 2 | `search-site/ai_search.py` | Expand `ask()` sources to include full product fields |
| 3 | `search-site/app.py` | Add `_find_local_record()`, enrich AI sources with `content_hash`, `page_type`, `locale`, `image` |
| 4 | `search-site/static/app.js` | Extract `renderProductCard()` from `renderResults()` |
| 5 | `search-site/static/app.js` | Update `doAiSearch()` to render cards instead of pills |
| 6 | `search-site/static/app.js` | Enhance `formatAiAnswer()` with markdown link parsing + URL rewriting |
| 7 | — | Manual testing |

---

## Rollback

All changes are additive to existing code. If issues arise:
- Revert `doAiSearch()` to render pills instead of cards (restore old `aiSourcesEl` block).
- Keyword search is untouched and unaffected.
- `ai_search.py` changes are backward-compatible (additional fields in response).
