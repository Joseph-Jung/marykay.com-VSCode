#!/usr/bin/env python3
"""
FAQ Scraper — Extracts FAQ Q&A pairs from Mary Kay contact-us page.
Uses Bootstrap accordion structure (pxp-faq-accordion / card / card-header / card-body).
Output: faq_records.jsonl
"""

import json
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

TARGET_URL = "https://www.marykay.com/en/contact-us.html"
SOURCE_URL = "https://www.marykay.com/en/contact-us.html#frequently-asked-questions"
USER_AGENT = "MaryKayCorpusBot/1.0 (educational-research)"
OUTPUT_FILE = Path(__file__).parent / "faq_records.jsonl"

# Known FAQ categories — used to filter out non-FAQ cards (e.g., cookie consent)
FAQ_CATEGORIES = {"Ordering Products", "Shipping & Delivery", "Become a Beauty Consultant"}


def make_id(category: str, question: str) -> str:
    """Generate a deterministic ID from category + question."""
    slug = re.sub(r"[^a-z0-9]+", "-", f"{category} {question}".lower()).strip("-")
    short_hash = hashlib.md5(slug.encode()).hexdigest()[:8]
    slug_trimmed = slug[:60].rstrip("-")
    return f"faq-{slug_trimmed}-{short_hash}"


def scrape_faqs() -> list[dict]:
    """Fetch the contact-us page and extract FAQ Q&A pairs."""
    print(f"Fetching {TARGET_URL} ...")
    resp = httpx.get(TARGET_URL, headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    faqs = []
    now = datetime.now(timezone.utc).isoformat()

    # The page uses Bootstrap accordion cards inside .pxp-faq-accordion divs.
    # Category headlines are h2.pxp-faq-category-headline elements preceding each accordion.
    # Each card has .card-header (question) and .card-body (answer).
    for card_header in soup.find_all(class_="card-header"):
        card = card_header.parent
        if not card:
            continue

        card_body = card.find(class_="card-body")
        if not card_body:
            continue

        question = card_header.get_text(strip=True)
        answer = card_body.get_text(" ", strip=True)

        if not question or not answer:
            continue

        # Find the nearest preceding category headline
        category_el = card_header.find_previous(class_="pxp-faq-category-headline")
        category = category_el.get_text(strip=True) if category_el else "General"

        # Skip non-FAQ cards (e.g., cookie consent cards use "Required", "Functional", etc.)
        if category not in FAQ_CATEGORIES:
            continue

        faqs.append({
            "id": make_id(category, question),
            "source_url": SOURCE_URL,
            "category": category,
            "question": question,
            "answer": answer,
            "content": f"Q: {question}\nA: {answer}",
            "page_type": "faq",
            "locale": "en_US",
            "scraped_at": now,
        })

    return faqs


def main():
    faqs = scrape_faqs()

    if not faqs:
        print("WARNING: No FAQ entries extracted. The page structure may have changed.")
        return

    # Deduplicate by question
    seen = set()
    unique = []
    for faq in faqs:
        if faq["question"] not in seen:
            seen.add(faq["question"])
            unique.append(faq)

    with open(OUTPUT_FILE, "w") as f:
        for record in unique:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Extracted {len(unique)} FAQ records → {OUTPUT_FILE}")
    for faq in unique:
        print(f"  [{faq['category']}] {faq['question']}")


if __name__ == "__main__":
    main()
