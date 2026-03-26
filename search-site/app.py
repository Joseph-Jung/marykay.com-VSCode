#!/usr/bin/env python3
"""
Mary Kay Search Website — Backend
Hybrid BM25 + TF-IDF search over the scraped MaryKay corpus.
"""

import os
# Prevent macOS fork+ObjC crash when gunicorn forks worker processes.
# The _scproxy module triggers ObjC class initialization in forked children,
# which is not allowed and causes SIGABRT.
os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")
os.environ.setdefault("no_proxy", "*")

import json
import math
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer

from ai_search import ask as ai_search_ask, search_products as ai_search_products

# ── Configuration ──────────────────────────────────────────────────────────────

DATA_PATH = Path(__file__).parent / "data" / "documents.jsonl"
STATIC_DIR = Path(__file__).parent / "static"
RESULTS_PER_PAGE = 12
BM25_WEIGHT = 0.6
TFIDF_WEIGHT = 0.4
PRODUCT_BOOST = 1.2

# ── Data Loading ───────────────────────────────────────────────────────────────

records = []
record_map = {}        # content_hash → record
search_texts = []      # parallel to records, for TF-IDF
bm25_corpus = []       # tokenized, for BM25
categories_set = set()

def extract_product_image(rec: dict) -> dict:
    """Pick the best product image from a record."""
    for img in rec.get("images", []):
        src = img.get("src", "")
        if "PRD" in src or "hi-res" in src.lower() or "product" in src.lower():
            return img
    # Fallback: first non-logo image
    for img in rec.get("images", []):
        src = img.get("src", "")
        alt = img.get("alt", "").lower()
        if "logo" not in src.lower() and "logo" not in alt and "icon" not in alt:
            return img
    return {"src": "", "alt": ""}


def extract_price(rec: dict) -> str:
    """Try to get price from main_text if product_fields.price is empty."""
    price = rec.get("product_fields", {}).get("price", "")
    if price:
        return price
    # Parse from main_text — look for $XX.XX pattern
    match = re.search(r'\$\d+\.\d{2}', rec.get("main_text", ""))
    if match:
        return match.group(0)
    return ""


def extract_category(rec: dict) -> str:
    """Get category from breadcrumbs or URL path."""
    pf = rec.get("product_fields", {})
    if pf.get("category"):
        return pf["category"]
    breadcrumbs = rec.get("breadcrumbs", [])
    if breadcrumbs:
        return " > ".join(breadcrumbs)
    # Fall back to URL path segments
    from urllib.parse import urlparse
    path = urlparse(rec.get("url", "")).path
    parts = [p for p in path.split("/") if p and p not in ("en", "es")]
    if parts:
        return parts[0].replace("-", " ").title()
    return "Other"


def classify_page_type(url: str) -> str:
    """Classify URL into page type."""
    path = url.lower()
    if re.search(r'/\d+US', path, re.IGNORECASE):
        return "product"
    if any(x in path for x in ["/discover/", "how-to", "skin-care-101", "about-mary-kay",
                                 "build-a-skin-care-routine", "ingredient-glossary",
                                 "what-skin-type", "contact-us", "be-a-beauty-consultant"]):
        return "content"
    return "category"


def tokenize(text: str) -> list:
    """Simple tokenizer for BM25."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = text.split()
    # Remove very short tokens
    return [t for t in tokens if len(t) > 1]


def build_search_text(rec: dict) -> str:
    """Build boosted search text for a record."""
    title = rec.get("title", "")
    h1 = rec.get("h1", "")
    product_name = rec.get("product_fields", {}).get("name", "")
    headings = " ".join(h.get("text", "") for h in rec.get("headings", []))
    meta = rec.get("meta_description", "")
    main = rec.get("main_text", "")
    breadcrumbs = " ".join(rec.get("breadcrumbs", []))
    benefits = " ".join(rec.get("product_fields", {}).get("key_benefits", []))
    faq_text = " ".join(
        f"{fq.get('question', '')} {fq.get('answer', '')}"
        for fq in rec.get("faq_pairs", [])
    )

    return (
        f"{title} {title} {title} "        # 3x boost
        f"{h1} {h1} "                       # 2x boost
        f"{product_name} {product_name} "   # 2x boost
        f"{headings} "
        f"{meta} "
        f"{breadcrumbs} "
        f"{benefits} "
        f"{faq_text} "
        f"{main}"
    )


def load_data():
    """Load corpus and build search indices."""
    global records, record_map, search_texts, bm25_corpus, categories_set
    global bm25_index, tfidf_vectorizer, tfidf_matrix

    print("Loading corpus...")
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            # Enrich with derived fields
            rec["_image"] = extract_product_image(rec)
            rec["_price"] = extract_price(rec)
            rec["_category"] = extract_category(rec)
            rec["_page_type"] = classify_page_type(rec.get("url", ""))
            records.append(rec)
            record_map[rec["content_hash"]] = rec
            categories_set.add(rec["_category"].split(" > ")[0] if " > " in rec["_category"] else rec["_category"])

    print(f"  Loaded {len(records)} records")

    # Build search texts
    for rec in records:
        st = build_search_text(rec)
        search_texts.append(st)
        bm25_corpus.append(tokenize(st))

    # BM25 index
    print("  Building BM25 index...")
    bm25_index = BM25Okapi(bm25_corpus)

    # TF-IDF index
    print("  Building TF-IDF index...")
    tfidf_vectorizer = TfidfVectorizer(
        max_features=10000,
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    tfidf_matrix = tfidf_vectorizer.fit_transform(search_texts)

    print("  Index ready!")


# ── Search Engine ──────────────────────────────────────────────────────────────

def hybrid_search(query: str, locale: Optional[str] = None,
                  category: Optional[str] = None,
                  page_type: Optional[str] = None,
                  page: int = 1) -> dict:
    """Perform hybrid BM25 + TF-IDF search."""
    if not query.strip():
        # Return all records (browse mode)
        filtered = records
        if locale:
            filtered = [r for r in filtered if r.get("locale") == locale]
        if category:
            filtered = [r for r in filtered if category.lower() in r["_category"].lower()]
        if page_type:
            filtered = [r for r in filtered if r["_page_type"] == page_type]

        total = len(filtered)
        start = (page - 1) * RESULTS_PER_PAGE
        end = start + RESULTS_PER_PAGE
        page_records = filtered[start:end]

        return {
            "query": "",
            "total_results": total,
            "page": page,
            "total_pages": math.ceil(total / RESULTS_PER_PAGE),
            "results": [format_result(r, 1.0, "") for r in page_records],
            "facets": build_facets(filtered),
        }

    # Tokenize query
    query_tokens = tokenize(query)
    if not query_tokens:
        return {"query": query, "total_results": 0, "page": 1, "total_pages": 0,
                "results": [], "facets": build_facets([])}

    # BM25 scores
    bm25_scores = bm25_index.get_scores(query_tokens)
    bm25_max = max(bm25_scores) if max(bm25_scores) > 0 else 1.0

    # TF-IDF scores
    query_vec = tfidf_vectorizer.transform([query])
    tfidf_scores = (tfidf_matrix @ query_vec.T).toarray().flatten()
    tfidf_max = max(tfidf_scores) if max(tfidf_scores) > 0 else 1.0

    # Combine scores
    scored = []
    for i, rec in enumerate(records):
        bm25_norm = bm25_scores[i] / bm25_max
        tfidf_norm = tfidf_scores[i] / tfidf_max
        score = BM25_WEIGHT * bm25_norm + TFIDF_WEIGHT * tfidf_norm

        # Boost product pages
        if rec["_page_type"] == "product":
            score *= PRODUCT_BOOST

        # Apply filters
        if locale and rec.get("locale") != locale:
            continue
        if category and category.lower() not in rec["_category"].lower():
            continue
        if page_type and rec["_page_type"] != page_type:
            continue

        if score > 0.01:  # threshold
            scored.append((i, score))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # Deduplicate by content_hash
    seen = set()
    deduped = []
    for idx, score in scored:
        h = records[idx]["content_hash"]
        if h not in seen:
            seen.add(h)
            deduped.append((idx, score))

    total = len(deduped)
    start = (page - 1) * RESULTS_PER_PAGE
    end = start + RESULTS_PER_PAGE
    page_results = deduped[start:end]

    results = []
    for idx, score in page_results:
        rec = records[idx]
        snippet = extract_snippet(rec, query)
        results.append(format_result(rec, score, snippet))

    # Build facets from all matching results (not just current page)
    all_matching = [records[idx] for idx, _ in deduped]

    return {
        "query": query,
        "total_results": total,
        "page": page,
        "total_pages": math.ceil(total / RESULTS_PER_PAGE),
        "results": results,
        "facets": build_facets(all_matching),
    }


def format_result(rec: dict, score: float, snippet: str) -> dict:
    """Format a record for API response."""
    confidence = "high" if score > 0.7 else ("medium" if score > 0.4 else "low")
    return {
        "content_hash": rec["content_hash"],
        "title": rec.get("title", ""),
        "h1": rec.get("h1", ""),
        "product_name": rec.get("product_fields", {}).get("name", ""),
        "price": rec["_price"],
        "image_url": rec["_image"].get("src", ""),
        "image_alt": rec["_image"].get("alt", ""),
        "meta_description": rec.get("meta_description", ""),
        "category": rec["_category"],
        "page_type": rec["_page_type"],
        "url": rec.get("url", ""),
        "canonical_url": rec.get("canonical_url", ""),
        "locale": rec.get("locale", ""),
        "snippet": snippet or rec.get("meta_description", "")[:200],
        "score": round(score, 3),
        "confidence": confidence,
        "faq_count": len(rec.get("faq_pairs", [])),
    }


def extract_snippet(rec: dict, query: str, max_len: int = 250) -> str:
    """Extract a text snippet with query term context."""
    text = rec.get("main_text", "")
    query_terms = query.lower().split()

    # Find the best position — where most query terms cluster
    best_pos = 0
    best_score = 0
    text_lower = text.lower()

    for term in query_terms:
        pos = text_lower.find(term)
        if pos >= 0:
            # Score by how many other terms are nearby
            window = text_lower[max(0, pos - 100):pos + 100]
            score = sum(1 for t in query_terms if t in window)
            if score > best_score:
                best_score = score
                best_pos = max(0, pos - 80)

    snippet = text[best_pos:best_pos + max_len]
    if best_pos > 0:
        snippet = "..." + snippet
    if best_pos + max_len < len(text):
        snippet = snippet + "..."

    return snippet.strip()


def build_facets(matching_records: list) -> dict:
    """Build facet counts from matching records."""
    cat_counts = {}
    locale_counts = {}
    type_counts = {}

    for r in matching_records:
        cat = r["_category"].split(" > ")[0] if " > " in r["_category"] else r["_category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        loc = r.get("locale", "unknown")
        locale_counts[loc] = locale_counts.get(loc, 0) + 1
        pt = r["_page_type"]
        type_counts[pt] = type_counts.get(pt, 0) + 1

    return {
        "categories": sorted([{"name": k, "count": v} for k, v in cat_counts.items()],
                             key=lambda x: x["count"], reverse=True),
        "locales": sorted([{"name": k, "count": v} for k, v in locale_counts.items()],
                          key=lambda x: x["count"], reverse=True),
        "page_types": sorted([{"name": k, "count": v} for k, v in type_counts.items()],
                             key=lambda x: x["count"], reverse=True),
    }


# ── FastAPI App ────────────────────────────────────────────────────────────────

app = FastAPI(title="Mary Kay Search", version="1.0")


@app.on_event("startup")
def startup():
    load_data()


# Serve static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/search")
async def api_search(
    q: str = Query(default="", description="Search query"),
    locale: Optional[str] = Query(default=None, description="Filter by locale: en_US or es_US"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    page_type: Optional[str] = Query(default=None, description="Filter: product, category, content"),
    page: int = Query(default=1, ge=1, description="Page number"),
):
    return hybrid_search(q, locale=locale, category=category, page_type=page_type, page=page)


@app.get("/api/product/{content_hash}")
async def api_product(content_hash: str):
    rec = record_map.get(content_hash)
    if not rec:
        return {"error": "Product not found"}

    return {
        "content_hash": rec["content_hash"],
        "url": rec.get("url", ""),
        "canonical_url": rec.get("canonical_url", ""),
        "title": rec.get("title", ""),
        "h1": rec.get("h1", ""),
        "meta_description": rec.get("meta_description", ""),
        "breadcrumbs": rec.get("breadcrumbs", []),
        "headings": rec.get("headings", []),
        "main_text": rec.get("main_text", ""),
        "product_fields": rec.get("product_fields", {}),
        "price": rec["_price"],
        "category": rec["_category"],
        "page_type": rec["_page_type"],
        "image": rec["_image"],
        "all_images": rec.get("images", []),
        "faq_pairs": rec.get("faq_pairs", []),
        "language": rec.get("language", ""),
        "locale": rec.get("locale", ""),
        "last_modified": rec.get("last_modified", ""),
    }


@app.get("/api/categories")
async def api_categories():
    cats = {}
    for rec in records:
        cat = rec["_category"].split(" > ")[0] if " > " in rec["_category"] else rec["_category"]
        cats[cat] = cats.get(cat, 0) + 1
    return {"categories": sorted([{"name": k, "count": v} for k, v in cats.items()],
                                  key=lambda x: x["count"], reverse=True)}


def _find_local_record(url: str) -> Optional[dict]:
    """Find a local record matching an AI search result URL."""
    if not url:
        return None
    # Extract path portion for comparison
    from urllib.parse import urlparse
    source_path = urlparse(url).path.rstrip("/")
    for rec in record_map.values():
        rec_url = rec.get("canonical_url", "") or rec.get("url", "")
        rec_path = urlparse(rec_url).path.rstrip("/")
        if rec_path and rec_path == source_path:
            return rec
    return None


@app.post("/api/ai-search")
async def api_ai_search(request: Request):
    """AI-powered natural language product search using Azure AI Search + GPT-4.1."""
    body = await request.json()
    user_query = body.get("query", "").strip()
    if not user_query:
        return {"answer": "Please enter a question.", "sources": []}
    result = ai_search_ask(user_query)

    # Enrich sources with local record data for product card rendering
    enriched_sources = []
    for source in result.get("sources", []):
        # FAQ sources — pass through without local record matching
        if source.get("page_type") == "faq":
            source["content_hash"] = None
            source["image_url"] = ""
            source["image_alt"] = ""
            source["snippet"] = (source.get("main_text", "") or
                                 source.get("description", ""))[:300]
            source["locale"] = "en_US"
            enriched_sources.append(source)
            continue

        # Product/content sources — enrich with local record data
        local_rec = _find_local_record(source.get("url", ""))
        if local_rec:
            source["content_hash"] = local_rec["content_hash"]
            source["page_type"] = local_rec["_page_type"]
            source["locale"] = local_rec.get("locale", "")
            source["image_url"] = local_rec["_image"].get("src", "")
            source["image_alt"] = local_rec["_image"].get("alt", "")
            source["snippet"] = (source.get("description", "") or
                                 source.get("main_text", ""))[:200]
            # Use local price if AI search returned empty
            if not source.get("price"):
                source["price"] = local_rec["_price"]
        else:
            source["content_hash"] = None
            source["page_type"] = source.get("page_type") or "product"
            source["locale"] = ""
            source["image_url"] = (source.get("images", [None]) or [None])[0] or ""
            source["image_alt"] = source.get("product_name", "") or source.get("title", "")
            source["snippet"] = (source.get("description", "") or
                                 source.get("main_text", ""))[:200]
        enriched_sources.append(source)

    result["sources"] = enriched_sources
    return result


@app.get("/api/faq")
async def api_faq(
    q: str = Query(default="", description="FAQ search query"),
    locale: Optional[str] = Query(default=None),
):
    """Search across FAQ pairs specifically."""
    results = []
    query_lower = q.lower()

    for rec in records:
        if locale and rec.get("locale") != locale:
            continue
        for faq in rec.get("faq_pairs", []):
            question = faq.get("question", "")
            answer = faq.get("answer", "")
            if query_lower in question.lower() or query_lower in answer.lower():
                results.append({
                    "question": question,
                    "answer": answer,
                    "source_title": rec.get("title", ""),
                    "source_url": rec.get("canonical_url", rec.get("url", "")),
                    "product_name": rec.get("product_fields", {}).get("name", ""),
                })
        if len(results) >= 20:
            break

    return {"query": q, "total": len(results), "results": results}


# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
