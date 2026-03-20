#!/usr/bin/env python3
"""
Step 7 — Validate the marykay-products index:
  1. Document count
  2. Keyword searches
  3. Vector (hybrid) search
  4. Semantic-ranked search
"""

import os
import requests
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "search-site", ".env"))

SEARCH_ENDPOINT = os.environ["AZURE_AI_SEARCH_ENDPOINT"]
SEARCH_KEY = os.environ["AZURE_AI_SEARCH_KEY"]
INDEX_NAME = os.environ.get("AZURE_AI_SEARCH_INDEX", "marykay-products")
EMBEDDING_ENDPOINT = os.environ["EMBEDDING_MODEL_ENDPOINT"]
API_KEY = os.environ["API_KEY"]

client = SearchClient(SEARCH_ENDPOINT, INDEX_NAME, AzureKeyCredential(SEARCH_KEY))

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    status = "PASS" if condition else "FAIL"
    if not condition:
        failed += 1
    else:
        passed += 1
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


def get_embedding(text: str) -> list[float]:
    headers = {"Content-Type": "application/json", "api-key": API_KEY}
    resp = requests.post(EMBEDDING_ENDPOINT, headers=headers, json={"input": text})
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


# --- Test 1: Document count -------------------------------------------
print("\n1. Document Count")
count = client.get_document_count()
check("Index has 298 documents", count == 298, f"actual={count}")

# --- Test 2: Keyword searches -----------------------------------------
print("\n2. Keyword Searches")
keyword_queries = [
    ("cc cream spf", "CC Cream"),
    ("anti aging skincare", "anti-aging"),
    ("lipstick shades", "lipstick"),
    ("men skincare", "men"),
    ("moisturizer dry skin", "moisturizer"),
]

for query, label in keyword_queries:
    results = list(client.search(search_text=query, top=3, select=["title", "product_name"]))
    check(f'"{query}" returns results', len(results) > 0, f"{len(results)} results, top: {results[0]['title'][:60] if results else 'none'}...")

# --- Test 3: Vector (hybrid) search -----------------------------------
print("\n3. Vector (Hybrid) Search")
query_text = "lightweight foundation with sun protection"
query_vector = get_embedding(query_text)

results = list(client.search(
    search_text=query_text,
    vector_queries=[
        {
            "kind": "vector",
            "vector": query_vector,
            "k_nearest_neighbors": 5,
            "fields": "content_vector",
        }
    ],
    top=5,
    select=["title", "product_name", "price"],
))
check(
    f'Hybrid search "{query_text[:40]}..."',
    len(results) > 0,
    f"{len(results)} results, top: {results[0]['title'][:60] if results else 'none'}",
)

# --- Test 4: Semantic search ------------------------------------------
print("\n4. Semantic Search")
results = list(client.search(
    search_text="what is the best product for oily skin",
    query_type="semantic",
    semantic_configuration_name="marykay-semantic-config",
    top=5,
    select=["title", "product_name", "category"],
))
check(
    'Semantic search "best product for oily skin"',
    len(results) > 0,
    f"{len(results)} results, top: {results[0]['title'][:60] if results else 'none'}",
)

# --- Summary -----------------------------------------------------------
print(f"\n{'='*50}")
print(f"Validation: {passed} passed, {failed} failed")
if failed == 0:
    print("All checks passed!")
else:
    print("Some checks failed — review above.")
