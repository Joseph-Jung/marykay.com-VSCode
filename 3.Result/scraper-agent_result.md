# Scraper Agent — Result Report

**Date:** 2026-02-25
**Target:** https://www.marykay.com/
**Status:** COMPLETE

---

## Executive Summary

Successfully crawled **298 pages** from marykay.com (149 EN + 149 ES) with a **100% success rate** and **0 errors**. The structured corpus totals **5 MB** of deduplicated JSONL data with **2,252 FAQ pairs** extracted across all pages. All crawling was fully compliant with robots.txt directives.

---

## Compliance

| Requirement | Status |
|-------------|--------|
| robots.txt obeyed | Yes — all disallowed paths respected |
| Crawl-delay | 2.0s between requests (none specified; used conservative default) |
| No login/CAPTCHA bypass | Confirmed |
| No private data collected | Confirmed |
| Polite user-agent | `MaryKayCorpusBot/1.0 (educational-research)` |
| Max concurrency | 3 simultaneous requests |

Full compliance documentation: `compliance.json`

---

## Crawl Statistics

### Pilot Crawl (50 pages)

| Metric | Value |
|--------|-------|
| URLs crawled | 50 |
| Success rate | 100% |
| Errors | 0 |
| Avg response time | 1,163 ms |
| Duration | 62.7s |
| Pages by type | 14 product, 29 category, 4 content, 3 other |

### Full Crawl (298 pages)

| Metric | Value |
|--------|-------|
| URLs discovered (sitemap) | 300 (298 after excluding demandware internal URLs) |
| URLs crawled | 298 |
| Successful | 298 (100%) |
| Errors | 0 |
| Duplicates removed | 0 (all pages had unique content) |
| Avg response time | 1,261 ms |
| Total duration | 403.3s (~6.7 min) |
| Pages by type | 28 product, 190 category, 42 content, 38 other |

---

## Corpus Quality Metrics

| Field | Coverage |
|-------|----------|
| title | 298/298 (100%) |
| meta_description | 298/298 (100%) |
| h1 | 292/298 (98%) |
| breadcrumbs | 238/298 (80%) |
| product_fields.name | 292/298 (98%) |
| product_fields.price | 0/298 (0%) — prices rendered client-side via JS |
| faq_pairs | 298/298 (100%) — 2,252 total pairs |
| images | 298/298 (100%) |
| main_text | 298/298 (100%) — avg 2,708 chars/page |
| internal_links | 298/298 (100%) — avg 135 links/page |
| content_hash (unique) | 298/298 (100% unique) |
| Locales | 149 EN + 149 ES |

### Known Limitations

1. **Prices not captured** — marykay.com renders pricing via JavaScript (Salesforce Commerce Cloud / Demandware). A headless browser (Playwright) would be needed to extract dynamic pricing.
2. **Shade options** — shade swatches are loaded dynamically; same JS limitation applies.
3. **Ingredients list** — most product pages serve ingredients in collapsed JS widgets rather than static HTML.

---

## Deliverables

| File | Size | Description |
|------|------|-------------|
| `documents.jsonl` | 5,026,890 bytes | Full structured corpus (298 records) |
| `url_index.csv` | 62,466 bytes | URL index with title, hash, locale, type |
| `crawl_report.json` | 504 bytes | Full crawl statistics |
| `pilot_crawl_report.json` | 498 bytes | Pilot crawl statistics |
| `pilot_documents.jsonl` | 789,338 bytes | Pilot corpus (50 records) |
| `qa_samples.json` | 173,622 bytes | 10 QA sample records |
| `seed_urls.csv` | 23,748 bytes | Categorized seed URL list |
| `compliance.json` | 906 bytes | Compliance documentation |
| `scraper-agent_result.md` | this file | Result report |

---

## QA Sample Records (10)

The 10 QA samples in `qa_samples.json` include a diverse mix:

1. **Product page** — Mary Kay CC Cream SPF 15 (EN)
2. **Product page** — Chromafusion Eye Shadow (EN)
3. **Category page** — Men's Fragrance (EN)
4. **Content page** — Blackberry Vinyl makeup trend (EN)
5. **Category page** — Gifts for Her (EN)
6. **Category page** — Makeup Remover (EN)
7. **Category page** — Face Primer (EN)
8. **Category page** — Face Concealer (EN)
9. **Category page** — Eyeliner (EN)
10. **Category page** — Mascara & Lashes (EN)

---

## Data Schema (per record)

Each record in `documents.jsonl` follows this schema:

```json
{
  "url": "string",
  "canonical_url": "string",
  "title": "string",
  "meta_description": "string",
  "breadcrumbs": ["string"],
  "h1": "string",
  "headings": [{"level": 2, "text": "string"}],
  "main_text": "string",
  "product_fields": {
    "name": "string",
    "price": "string",
    "size": "string",
    "shade_options": ["string"],
    "key_benefits": ["string"],
    "ingredients": ["string"],
    "how_to_use": "string",
    "warnings": "string",
    "category": "string"
  },
  "faq_pairs": [{"question": "string", "answer": "string"}],
  "images": [{"src": "string", "alt": "string"}],
  "language": "string",
  "locale": "string",
  "last_modified": "string",
  "crawl_timestamp": "ISO-8601",
  "content_hash": "SHA-256",
  "internal_links": ["string"],
  "outbound_links": ["string"]
}
```

---

## Recommendations for Next Steps

1. **Dynamic content extraction** — Use Playwright/headless Chrome to capture prices, shade swatches, and ingredients loaded via JavaScript.
2. **Incremental re-crawl** — Use `content_hash` to detect changed pages and only re-process diffs.
3. **RAG chunking** — Split `main_text` into overlapping chunks (512-1024 tokens) for embedding and retrieval.
4. **Embedding generation** — Embed chunks using a model (e.g., text-embedding-3-small) and index in a vector store.
5. **Cross-locale linking** — EN and ES pages share the same products; link them via URL pattern matching for bilingual RAG.
