#!/usr/bin/env python3
"""
Step 6 — Ingest documents.jsonl into Azure AI Search index
with vector embeddings from text-embedding-3-large.
"""

import hashlib
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

# Load config
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "search-site", ".env"))

SEARCH_ENDPOINT = os.environ["AZURE_AI_SEARCH_ENDPOINT"]
SEARCH_KEY = os.environ["AZURE_AI_SEARCH_KEY"]
INDEX_NAME = os.environ.get("AZURE_AI_SEARCH_INDEX", "marykay-products")
EMBEDDING_ENDPOINT = os.environ["EMBEDDING_MODEL_ENDPOINT"]
API_KEY = os.environ["API_KEY"]

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "1.Order", "documents.jsonl")
BATCH_SIZE = 20  # documents per upload batch
EMBEDDING_BATCH_SIZE = 16  # texts per embedding API call


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Call Azure OpenAI embedding API for a batch of texts."""
    headers = {"Content-Type": "application/json", "api-key": API_KEY}
    body = {"input": texts}
    resp = requests.post(EMBEDDING_ENDPOINT, headers=headers, json=body)
    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", 10))
        print(f"  Rate limited. Waiting {retry_after}s ...")
        time.sleep(retry_after)
        return get_embeddings(texts)
    resp.raise_for_status()
    data = resp.json()["data"]
    return [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]


def transform_record(rec: dict, embedding: list[float]) -> dict:
    """Transform a JSONL record into the index schema."""
    pf = rec.get("product_fields") or {}
    canonical = rec.get("canonical_url", rec.get("url", ""))
    images_raw = rec.get("images", [])
    image_urls = []
    for img in images_raw:
        if isinstance(img, dict):
            image_urls.append(img.get("src", ""))
        elif isinstance(img, str):
            image_urls.append(img)

    return {
        "id": hashlib.sha256(canonical.encode()).hexdigest()[:32],
        "url": canonical,
        "title": rec.get("title", ""),
        "h1": rec.get("h1", ""),
        "description": rec.get("meta_description", ""),
        "main_text": rec.get("main_text", ""),
        "product_name": pf.get("name", ""),
        "price": pf.get("price", ""),
        "size": pf.get("size", ""),
        "category": pf.get("category", ""),
        "key_benefits": pf.get("key_benefits", []),
        "ingredients": pf.get("ingredients", []),
        "how_to_use": pf.get("how_to_use", ""),
        "shade_options": pf.get("shade_options", []),
        "images": image_urls,
        "content_vector": embedding,
    }


def build_composite_text(rec: dict) -> str:
    """Build the text to embed: title + h1 + main_text excerpt + key_benefits."""
    pf = rec.get("product_fields") or {}
    parts = [
        rec.get("title", ""),
        rec.get("h1", ""),
        (rec.get("main_text", "") or "")[:2000],  # cap to avoid token limits
        " ".join(pf.get("key_benefits", [])),
    ]
    return " ".join(p for p in parts if p).strip()


def main():
    # Load records
    records = []
    with open(DATA_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    print(f"Loaded {len(records)} records from {DATA_PATH}")

    search_client = SearchClient(SEARCH_ENDPOINT, INDEX_NAME, AzureKeyCredential(SEARCH_KEY))

    total_uploaded = 0
    total_errors = 0

    # Process in batches
    for i in range(0, len(records), BATCH_SIZE):
        batch_records = records[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"\nBatch {batch_num} ({i+1}–{i+len(batch_records)} of {len(records)})")

        # Build composite texts for embedding
        composite_texts = [build_composite_text(r) for r in batch_records]

        # Get embeddings in sub-batches
        all_embeddings = []
        for j in range(0, len(composite_texts), EMBEDDING_BATCH_SIZE):
            sub_batch = composite_texts[j : j + EMBEDDING_BATCH_SIZE]
            print(f"  Embedding {j+1}–{j+len(sub_batch)} ...")
            embeddings = get_embeddings(sub_batch)
            all_embeddings.extend(embeddings)
            time.sleep(0.5)  # gentle rate limiting

        # Transform records
        docs = []
        for rec, emb in zip(batch_records, all_embeddings):
            docs.append(transform_record(rec, emb))

        # Upload
        print(f"  Uploading {len(docs)} documents ...")
        result = search_client.upload_documents(documents=docs)
        succeeded = sum(1 for r in result if r.succeeded)
        failed = sum(1 for r in result if not r.succeeded)
        total_uploaded += succeeded
        total_errors += failed
        print(f"  Uploaded: {succeeded}, Failed: {failed}")

        if failed:
            for r in result:
                if not r.succeeded:
                    print(f"    Error [{r.key}]: {r.error_message}")

    print(f"\n{'='*50}")
    print(f"DONE — Total uploaded: {total_uploaded}, Total errors: {total_errors}")


if __name__ == "__main__":
    main()
