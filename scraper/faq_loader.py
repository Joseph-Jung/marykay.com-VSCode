#!/usr/bin/env python3
"""
FAQ Loader — Embeds FAQ records and uploads them to Azure AI Search.
Requires: search-site/.venv (has azure-search-documents, dotenv, requests)

Usage:
    source search-site/.venv/bin/activate
    python scraper/faq_loader.py
"""

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchFieldDataType,
    SimpleField,
)

# Load env
load_dotenv(Path(__file__).parent.parent / "search-site" / ".env")

SEARCH_ENDPOINT = os.environ["AZURE_AI_SEARCH_ENDPOINT"]
SEARCH_KEY = os.environ["AZURE_AI_SEARCH_KEY"]
INDEX_NAME = os.environ.get("AZURE_AI_SEARCH_INDEX", "marykay-products")
EMBEDDING_ENDPOINT = os.environ["EMBEDDING_MODEL_ENDPOINT"]
API_KEY = os.environ["API_KEY"]

FAQ_FILE = Path(__file__).parent / "faq_records.jsonl"


def ensure_page_type_field():
    """Add page_type field to the index if it doesn't exist."""
    index_client = SearchIndexClient(SEARCH_ENDPOINT, AzureKeyCredential(SEARCH_KEY))
    index = index_client.get_index(INDEX_NAME)

    existing_fields = {f.name for f in index.fields}
    if "page_type" in existing_fields:
        print("  page_type field already exists in index.")
        return

    print("  Adding page_type field to index...")
    index.fields.append(
        SimpleField(
            name="page_type",
            type=SearchFieldDataType.String,
            filterable=True,
            searchable=False,
        )
    )
    index_client.create_or_update_index(index)
    print("  page_type field added successfully.")


def get_embedding(text: str) -> list[float]:
    """Generate embedding using text-embedding-3-large."""
    headers = {"Content-Type": "application/json", "api-key": API_KEY}
    resp = requests.post(EMBEDDING_ENDPOINT, headers=headers, json={"input": text})
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


def load_faqs():
    """Load FAQ records, embed them, and upload to Azure AI Search."""
    if not FAQ_FILE.exists():
        print(f"ERROR: {FAQ_FILE} not found. Run faq_scraper.py first.")
        sys.exit(1)

    # Step 1: Ensure index has page_type field
    print("Step 1: Checking index schema...")
    ensure_page_type_field()

    # Step 2: Read FAQ records
    print(f"Step 2: Reading FAQ records from {FAQ_FILE}...")
    faq_records = []
    with open(FAQ_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                faq_records.append(json.loads(line))
    print(f"  Found {len(faq_records)} FAQ records.")

    # Step 3: Generate embeddings and build index documents
    print("Step 3: Generating embeddings...")
    documents = []
    for i, faq in enumerate(faq_records):
        print(f"  [{i+1}/{len(faq_records)}] Embedding: {faq['question'][:60]}...")
        embedding = get_embedding(faq["content"])

        doc = {
            "id": faq["id"],
            "url": faq["source_url"],
            "title": faq["question"],
            "h1": faq["question"],
            "description": faq["content"],
            "main_text": faq["answer"],
            "product_name": "",
            "price": "",
            "size": "",
            "category": faq["category"],
            "key_benefits": [],
            "ingredients": [],
            "how_to_use": "",
            "shade_options": [],
            "images": [],
            "content_vector": embedding,
            "page_type": "faq",
        }
        documents.append(doc)

    # Step 4: Upload to Azure AI Search
    print("Step 4: Uploading to Azure AI Search...")
    search_client = SearchClient(SEARCH_ENDPOINT, INDEX_NAME, AzureKeyCredential(SEARCH_KEY))
    result = search_client.merge_or_upload_documents(documents)

    succeeded = sum(1 for r in result if r.succeeded)
    failed = sum(1 for r in result if not r.succeeded)
    print(f"  Upload complete: {succeeded} succeeded, {failed} failed.")

    if failed:
        for r in result:
            if not r.succeeded:
                print(f"  FAILED: {r.key} — {r.error_message}")

    print("Done!")


if __name__ == "__main__":
    load_faqs()
