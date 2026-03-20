#!/usr/bin/env python3
"""
AI Search module — Azure AI Search + GPT-4.1 RAG pipeline.
Provides:
  - search_products(query, top_k, locale) → list of product dicts
  - ask(user_query, locale) → {"answer": ..., "sources": [...]}
"""

import os
import requests
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from dotenv import load_dotenv

# Load env from .env file (no-op if already loaded)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SEARCH_ENDPOINT = os.environ["AZURE_AI_SEARCH_ENDPOINT"]
SEARCH_KEY = os.environ["AZURE_AI_SEARCH_KEY"]
INDEX_NAME = os.environ.get("AZURE_AI_SEARCH_INDEX", "marykay-products")
CHAT_MODEL_ENDPOINT = os.environ["CHAT_MODEL_ENDPOINT"]
EMBEDDING_ENDPOINT = os.environ["EMBEDDING_MODEL_ENDPOINT"]
API_KEY = os.environ["API_KEY"]

_search_client = SearchClient(SEARCH_ENDPOINT, INDEX_NAME, AzureKeyCredential(SEARCH_KEY))


def _get_embedding(text: str) -> list[float]:
    """Generate embedding for a query string."""
    headers = {"Content-Type": "application/json", "api-key": API_KEY}
    resp = requests.post(EMBEDDING_ENDPOINT, headers=headers, json={"input": text})
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


def search_products(query: str, top_k: int = 5) -> list[dict]:
    """
    Hybrid search: keyword + vector + semantic reranking.
    Returns top_k product results with key fields.
    """
    query_vector = _get_embedding(query)

    results = _search_client.search(
        search_text=query,
        vector_queries=[
            {
                "kind": "vector",
                "vector": query_vector,
                "k_nearest_neighbors": top_k * 2,
                "fields": "content_vector",
            }
        ],
        query_type="semantic",
        semantic_configuration_name="marykay-semantic-config",
        top=top_k,
        select=[
            "title", "url", "h1", "description", "main_text",
            "product_name", "price", "size", "category",
            "key_benefits", "shade_options", "images",
        ],
    )

    products = []
    for r in results:
        products.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "h1": r.get("h1", ""),
            "description": r.get("description", ""),
            "main_text": r.get("main_text", ""),
            "product_name": r.get("product_name", ""),
            "price": r.get("price", ""),
            "size": r.get("size", ""),
            "category": r.get("category", ""),
            "key_benefits": r.get("key_benefits", []),
            "shade_options": r.get("shade_options", []),
            "images": r.get("images", []),
            "score": r.get("@search.score", 0),
            "reranker_score": r.get("@search.reranker_score", None),
        })
    return products


def ask(user_query: str) -> dict:
    """
    Natural language product search with grounded GPT-4.1 answer.
    Returns {"answer": str, "sources": [{"title", "url", "product_name", "price"}]}
    """
    # Step 1: Retrieve relevant products
    search_results = search_products(user_query, top_k=5)

    if not search_results:
        return {
            "answer": "I couldn't find any products matching your query. Please try rephrasing or searching for a different product.",
            "sources": [],
        }

    # Step 2: Build grounding context
    context_parts = []
    for i, r in enumerate(search_results, 1):
        name = r["product_name"] or r["title"]
        benefits = ", ".join(r.get("key_benefits", [])) if r.get("key_benefits") else "N/A"
        shades = ", ".join(r.get("shade_options", [])) if r.get("shade_options") else "N/A"
        text_excerpt = (r.get("main_text", "") or "")[:600]

        context_parts.append(
            f"[Product {i}]\n"
            f"Name: {name}\n"
            f"Price: {r['price']}\n"
            f"Size: {r['size']}\n"
            f"Category: {r['category']}\n"
            f"Key Benefits: {benefits}\n"
            f"Shade Options: {shades}\n"
            f"URL: {r['url']}\n"
            f"Description: {text_excerpt}\n"
        )

    context = "\n---\n".join(context_parts)

    # Step 3: Call GPT-4.1
    system_prompt = (
        "You are a Mary Kay product advisor. Answer the user's question "
        "using ONLY the product information provided below. "
        "Be helpful, concise, and specific. "
        "Always mention product names and prices when relevant. "
        "Cite the product URL for each product you mention. "
        "If the answer is not in the provided context, say so clearly.\n\n"
        f"## Product Context\n\n{context}"
    )

    headers = {"Content-Type": "application/json", "api-key": API_KEY}
    body = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
    }

    resp = requests.post(CHAT_MODEL_ENDPOINT, headers=headers, json=body)
    resp.raise_for_status()
    answer = resp.json()["choices"][0]["message"]["content"]

    # Step 4: Return answer + sources
    sources = [
        {
            "title": r["title"],
            "url": r["url"],
            "product_name": r["product_name"],
            "price": r["price"],
            "images": r["images"],
        }
        for r in search_results
    ]

    return {"answer": answer, "sources": sources}
