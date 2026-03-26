# Scraper Agent — Implementation Plan

## Overview

Build a compliant web crawler and structured content extractor for
marykay.com, producing a deduplicated corpus optimized for RAG.

---

## Phase 0: Compliance Check

| Step | Action | Output |
|------|--------|--------|
| 0.1 | Fetch and parse `https://www.marykay.com/robots.txt` | List of allowed/disallowed paths, crawl-delay value, sitemap URLs |
| 0.2 | Review Terms of Service page for scraping restrictions | Go/No-Go decision |
| 0.3 | Document compliance constraints | `compliance.json` — allowed paths, rate limits, restrictions |

**Gate:** If robots.txt blocks `*` from key paths or ToS explicitly prohibits scraping, STOP and report to user.

---

## Phase 1: URL Discovery & Seed List

| Step | Action | Output |
|------|--------|--------|
| 1.1 | Parse sitemap.xml (and any sitemap index entries) | Raw URL list |
| 1.2 | Categorize URLs by type (product, category, content/editorial, FAQ, other) | Categorized seed list |
| 1.3 | Normalize URLs — strip tracking params (`utm_*`, `gclid`, `fbclid`), deduplicate, prefer canonical | `seed_urls.csv` with columns: `url`, `type`, `priority` |

**Expected volume:** Estimate total page count from sitemap; flag if > 10,000 pages.

---

## Phase 2: Scraper Development

### 2.1 Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.11+ | Ecosystem maturity for scraping |
| HTTP client | `httpx` (async) | Async support, HTTP/2, connection pooling |
| HTML parser | `BeautifulSoup4` + `lxml` | Robust parsing, handles malformed HTML |
| Rate limiting | Custom token-bucket or `asyncio.Semaphore` | Respect crawl-delay |
| Output format | JSONL | Streaming writes, line-level append |
| Hashing | SHA-256 on `main_text` | Content deduplication |

### 2.2 Core Modules

```
scraper/
├── __init__.py
├── config.py          # Constants, rate limits, user-agent
├── compliance.py      # robots.txt parser, rate limiter
├── url_manager.py     # Seed list, queue, dedup, normalization
├── fetcher.py         # Async HTTP client with retry/backoff
├── parser.py          # HTML → structured record (generic pages)
├── product_parser.py  # Product-specific field extraction
├── faq_parser.py      # FAQ pair extraction
├── pipeline.py        # Orchestrator: fetch → parse → write
├── quality.py         # Validation, stats, QA sampling
└── main.py            # CLI entry point
```

### 2.3 Crawl Behavior

- **User-Agent:** Descriptive, non-deceptive (e.g., `MaryKayCorpusBot/1.0 (+contact)`)
- **Crawl-delay:** Honor robots.txt value; default to 2 seconds minimum between requests
- **Retry:** Exponential backoff (1s → 2s → 4s → 8s), max 3 retries
- **Timeout:** 30s per request
- **Concurrency:** Max 3 concurrent requests (adjustable)
- **Error handling:** Log and skip on 4xx/5xx; do not crash the pipeline

---

## Phase 3: Parser Logic

### 3.1 Generic Page Extraction

| Field | Source |
|-------|--------|
| `url` | Request URL |
| `canonical_url` | `<link rel="canonical">` |
| `title` | `<title>` tag |
| `meta_description` | `<meta name="description">` |
| `breadcrumbs` | Breadcrumb nav element (schema.org or CSS selectors) |
| `h1` | First `<h1>` |
| `headings` | All `<h2>`–`<h6>` text |
| `main_text` | Largest content block (strip nav/footer/sidebar) |
| `images` | `<img>` src + alt within main content |
| `language` | `<html lang="">` |
| `locale` | URL path segment or meta tag |
| `last_modified` | HTTP header or `<meta>` |
| `crawl_timestamp` | ISO-8601 at fetch time |
| `content_hash` | SHA-256 of `main_text` |
| `internal_links` | `<a href>` pointing to marykay.com |
| `outbound_links` | `<a href>` pointing elsewhere |

### 3.2 Product Page Extraction (extends generic)

| Field | Source |
|-------|--------|
| `product_fields.name` | Product title element / schema.org `Product.name` |
| `product_fields.price` | Price element / schema.org `Product.offers.price` |
| `product_fields.size` | Size/volume element |
| `product_fields.shade_options` | Shade selector options |
| `product_fields.key_benefits` | Benefits list/section |
| `product_fields.ingredients` | Ingredients section |
| `product_fields.how_to_use` | Usage instructions section |
| `product_fields.warnings` | Warnings/cautions section |
| `product_fields.category` | Breadcrumb or category tag |

### 3.3 FAQ Extraction

- Look for FAQ schema markup (`FAQPage`, `Question`/`Answer`)
- Fallback: accordion/toggle patterns in HTML
- Output: `[{"question": "...", "answer": "..."}]`

---

## Phase 4: Pilot Crawl (50 pages)

| Step | Action | Output |
|------|--------|--------|
| 4.1 | Select 50 seed URLs (mix of product, category, content, FAQ) | Pilot seed list |
| 4.2 | Run scraper on pilot set | `pilot_documents.jsonl` |
| 4.3 | Validate schema completeness — every record has required fields | Validation report |
| 4.4 | Manual QA — spot-check 10 records against live pages | QA report with pass/fail |
| 4.5 | Check deduplication — no duplicate `content_hash` values | Dedup stats |
| 4.6 | Review crawl stats (success rate, avg response time, errors) | `pilot_crawl_report.json` |

**Gate:** Fix any parser issues before proceeding to full crawl.

---

## Phase 5: Full Crawl

| Step | Action | Output |
|------|--------|--------|
| 5.1 | Load full seed list from Phase 1 | URL queue |
| 5.2 | Run pipeline with checkpointing (resume on failure) | `documents.jsonl` (append) |
| 5.3 | Discover new internal links during crawl; add to queue if unseen | Expanded URL set |
| 5.4 | Deduplicate by `content_hash` post-crawl | Final `documents.jsonl` |
| 5.5 | Generate `url_index.csv` (url, canonical_url, title, content_hash, status) | `url_index.csv` |
| 5.6 | Generate `crawl_report.json` | See schema below |

### crawl_report.json Schema

```json
{
  "total_urls_discovered": 0,
  "total_urls_crawled": 0,
  "total_urls_skipped": 0,
  "total_duplicates_removed": 0,
  "success_count": 0,
  "error_count": 0,
  "errors_by_status_code": {},
  "avg_response_time_ms": 0,
  "crawl_start": "",
  "crawl_end": "",
  "crawl_duration_seconds": 0,
  "pages_by_type": {
    "product": 0,
    "category": 0,
    "content": 0,
    "faq": 0,
    "other": 0
  }
}
```

---

## Phase 6: Quality Control & Deliverables

| Step | Action | Output |
|------|--------|--------|
| 6.1 | Final deduplication pass | Clean `documents.jsonl` |
| 6.2 | Schema validation — every record matches spec | Validation log |
| 6.3 | Select 10 QA sample records (diverse page types) | `qa_samples.json` |
| 6.4 | Generate final statistics | `crawl_report.json` |

### Final Deliverables

```
3.Result/
├── documents.jsonl          # Full structured corpus
├── url_index.csv            # URL → title → hash index
├── crawl_report.json        # Crawl statistics
├── qa_samples.json          # 10 QA sample records
└── compliance.json          # Compliance constraints documented
```

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| robots.txt blocks key paths | Check upfront in Phase 0; abort if critical |
| Site uses heavy JS rendering | Detect during pilot; fall back to `playwright` if needed |
| Rate limiting / IP blocking | Respect crawl-delay, use exponential backoff, cap concurrency |
| Schema.org markup absent | Use CSS selector fallbacks per page type |
| Very large site (>50k pages) | Prioritize product + content pages; skip duplicative filter URLs |
| Content behind login/age-gate | Skip those pages; document in crawl report |

---

## Execution Order Summary

```
Phase 0  →  Compliance Check (GO/NO-GO)
Phase 1  →  URL Discovery & Seed List
Phase 2  →  Scraper Development
Phase 3  →  Parser Logic (built during Phase 2)
Phase 4  →  Pilot Crawl (50 pages) — validate & fix
Phase 5  →  Full Crawl
Phase 6  →  QC & Deliverables
```
