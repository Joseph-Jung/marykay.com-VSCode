#!/usr/bin/env python3
"""
Step 5 — Create Azure AI Search index 'marykay-products'
with text fields, vector search, and semantic ranking.
"""

import os
import sys
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField,
)

# Load config
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "search-site", ".env"))

SEARCH_ENDPOINT = os.environ["AZURE_AI_SEARCH_ENDPOINT"]
SEARCH_KEY = os.environ["AZURE_AI_SEARCH_KEY"]
INDEX_NAME = os.environ.get("AZURE_AI_SEARCH_INDEX", "marykay-products")

# --- Fields -----------------------------------------------------------

fields = [
    SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
    SimpleField(name="url", type=SearchFieldDataType.String, filterable=True),
    SearchableField(name="title", type=SearchFieldDataType.String),
    SearchableField(name="h1", type=SearchFieldDataType.String),
    SearchableField(name="description", type=SearchFieldDataType.String),
    SearchableField(name="main_text", type=SearchFieldDataType.String),
    SearchableField(name="product_name", type=SearchFieldDataType.String, filterable=True, facetable=True),
    SearchableField(name="price", type=SearchFieldDataType.String, filterable=True, facetable=True),
    SearchableField(name="size", type=SearchFieldDataType.String),
    SearchableField(name="category", type=SearchFieldDataType.String, filterable=True, facetable=True),
    SearchableField(name="key_benefits", type=SearchFieldDataType.String, collection=True),
    SearchableField(name="ingredients", type=SearchFieldDataType.String, collection=True),
    SearchableField(name="how_to_use", type=SearchFieldDataType.String),
    SearchableField(name="shade_options", type=SearchFieldDataType.String, collection=True, filterable=True, facetable=True),
    SimpleField(name="images", type=SearchFieldDataType.Collection(SearchFieldDataType.String)),
    SearchField(
        name="content_vector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        searchable=True,
        vector_search_dimensions=3072,  # text-embedding-3-large
        vector_search_profile_name="marykay-vector-profile",
    ),
]

# --- Vector search config ---------------------------------------------

vector_search = VectorSearch(
    algorithms=[
        HnswAlgorithmConfiguration(name="marykay-hnsw"),
    ],
    profiles=[
        VectorSearchProfile(
            name="marykay-vector-profile",
            algorithm_configuration_name="marykay-hnsw",
        ),
    ],
)

# --- Semantic search config --------------------------------------------

semantic_config = SemanticConfiguration(
    name="marykay-semantic-config",
    prioritized_fields=SemanticPrioritizedFields(
        title_field=SemanticField(field_name="title"),
        content_fields=[
            SemanticField(field_name="main_text"),
        ],
        keywords_fields=[
            SemanticField(field_name="key_benefits"),
            SemanticField(field_name="category"),
        ],
    ),
)

semantic_search = SemanticSearch(configurations=[semantic_config])

# --- Create index ------------------------------------------------------

index = SearchIndex(
    name=INDEX_NAME,
    fields=fields,
    vector_search=vector_search,
    semantic_search=semantic_search,
)

client = SearchIndexClient(SEARCH_ENDPOINT, AzureKeyCredential(SEARCH_KEY))

print(f"Creating index '{INDEX_NAME}' on {SEARCH_ENDPOINT} ...")
result = client.create_or_update_index(index)
print(f"Index '{result.name}' created/updated successfully.")
print(f"  Fields: {len(result.fields)}")
print(f"  Vector profiles: {[p.name for p in result.vector_search.profiles]}")
print(f"  Semantic configs: {[c.name for c in result.semantic_search.configurations]}")
