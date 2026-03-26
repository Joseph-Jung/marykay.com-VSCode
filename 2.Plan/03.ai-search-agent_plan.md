# AI Search Agent — Execution Plan

## Goal

Stand up end-to-end natural language product search: ingest 298 Mary Kay product records from `documents.jsonl` into **Azure AI Search**, wire it to **GPT-4.1** via Microsoft Foundry, and expose a RAG query pipeline — replacing the local BM25/TF-IDF search.

---

## Prerequisites

| Item | Status |
|------|--------|
| Microsoft Foundry project provisioned | Ready |
| GPT-4.1 chat model deployed | Ready |
| API key available | Ready |
| `1.Order/documents.jsonl` (298 records) | Ready |
| Existing search-site (FastAPI + static frontend) | Ready — will be extended |

---

## Step-by-Step Execution

### Step 1 — Install Python dependencies

**Executor:** Claude (automated)

Add Azure SDKs to the project so all subsequent scripts can run.

```
pip install azure-search-documents azure-identity openai python-dotenv
```

Update `search-site/requirements.txt` to include the new packages.

---

### Step 2 — Create `.env` file with Foundry credentials

**Executor:** Claude (automated)

Create a `.env` file at project root with all required configuration. API keys will be referenced from environment variables — never hardcoded in scripts.

```env
AIPROJECT_ENDPOINT=https://josephjung-7921-resource.services.ai.azure.com/api/projects/josephjung-7921
CHAT_MODEL_ENDPOINT=https://josephjung-7921.cognitiveservices.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2024-05-01-preview
CHAT_MODEL=gpt-4.1
API_KEY=<your-api-key>
AZURE_AI_SEARCH_ENDPOINT=<to-be-filled-after-step-3>
AZURE_AI_SEARCH_KEY=<to-be-filled-after-step-3>
AZURE_AI_SEARCH_INDEX=marykay-products
```

Add `.env` to `.gitignore`.

---

### Step 3 — Provision Azure AI Search resource

> **MANUAL STEP — Admin Console Required**

Azure AI Search cannot be created via the Search SDK — it must be provisioned as an Azure resource.

**Actions for you (Azure Portal or Foundry Portal):**

1. Go to [Azure Portal](https://portal.azure.com) → **Create a resource** → **Azure AI Search**.
2. Choose the same **Resource Group** and **Region** as your Foundry project (`josephjung-7921-resource`).
3. Select pricing tier:
   - **Free (F)** tier is sufficient for 298 documents / development.
   - **Basic (B)** tier if you want semantic ranker (required for semantic search).
   - Recommendation: **Basic** to enable semantic ranking.
4. Once created, go to the resource → **Keys** → copy:
   - **Service endpoint** (e.g., `https://<name>.search.windows.net`)
   - **Admin key** (primary)
5. Update `.env` with these two values:
   ```
   AZURE_AI_SEARCH_ENDPOINT=https://<your-search-name>.search.windows.net
   AZURE_AI_SEARCH_KEY=<admin-key>
   ```

**Alternatively**, if Azure AI Search is already connected to your Foundry project:
- Go to Foundry Portal → your project → **Connected resources** → check if a Search resource exists.
- If yes, grab the endpoint and key from there.

**Deliverable:** Search endpoint URL and admin key added to `.env`.

---

### Step 4 — Check if an embedding model is deployed

> **MANUAL STEP — Admin Console Required (if not already deployed)**

Vector search requires an embedding model. Check your Foundry project:

1. Go to Foundry Portal → **Models + endpoints** (or Azure OpenAI Studio → **Deployments**).
2. Look for an embedding model deployment (e.g., `text-embedding-3-large` or `text-embedding-ada-002`).
3. **If exists:** note the deployment name and endpoint. Add to `.env`:
   ```
   EMBEDDING_MODEL_ENDPOINT=https://josephjung-7921.cognitiveservices.azure.com/openai/deployments/<embedding-deployment-name>/embeddings?api-version=2024-05-01-preview
   EMBEDDING_MODEL=<deployment-name>
   ```
4. **If not exists:** Deploy one:
   - Go to **Deployments** → **Deploy model** → select `text-embedding-3-large` → Deploy.
   - Then add endpoint/name to `.env`.

**Deliverable:** Embedding model deployment name and endpoint in `.env`.

---

### Step 5 — Create the search index programmatically

**Executor:** Claude (automated)

Write and run a Python script `scripts/create_index.py` that:

1. Loads config from `.env`.
2. Connects to Azure AI Search using the admin key.
3. Defines the index schema:
   - Text fields: `id`, `url`, `title`, `h1`, `description`, `main_text`, `product_name`, `price`, `size`, `category`, `how_to_use`
   - Collection fields: `key_benefits`, `ingredients`, `shade_options`, `images`
   - Vector field: `content_vector` (dimensions matching the embedding model, e.g., 3072 for `text-embedding-3-large`, 1536 for `text-embedding-ada-002`)
4. Configures **semantic ranking** (semantic configuration on `title`, `main_text`, `key_benefits`).
5. Configures **vector search** profile (HNSW algorithm, cosine similarity).
6. Creates (or updates) the index via the SDK.

```python
# Key API calls:
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType,
    VectorSearch, HnswAlgorithmConfiguration, VectorSearchProfile,
    SemanticConfiguration, SemanticSearch, SemanticPrioritizedFields, SemanticField,
)

# ... define fields, semantic config, vector config ...
index = SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search, semantic_search=semantic_search)
index_client.create_or_update_index(index)
```

**Deliverable:** `marykay-products` index created in Azure AI Search with full schema.

---

### Step 6 — Ingest documents into the index

**Executor:** Claude (automated)

Write and run a Python script `scripts/ingest_data.py` that:

1. Reads `1.Order/documents.jsonl` (298 records).
2. For each record:
   - Flattens `product_fields` into top-level fields.
   - Generates a stable `id` from SHA-256 of `canonical_url`.
   - Builds a composite text: `title + h1 + main_text + key_benefits`.
   - Calls the **embedding model endpoint** to generate a vector for the composite text.
3. Uploads documents in batches of 50 (to stay within rate limits for embedding calls).
4. Prints upload results and error count.

**Rate limiting considerations:**
- Embedding API calls: batch the text inputs where possible (Azure OpenAI supports batch embedding).
- Search upload: batch size of 50–100 documents per call.
- Add retry logic with exponential backoff for transient failures.

**Deliverable:** 298 documents indexed with vectors in `marykay-products`.

---

### Step 7 — Validate the index

**Executor:** Claude (automated)

Write and run a validation script `scripts/validate_index.py` that:

1. Queries the index for total document count (expect 298).
2. Runs 5 sample keyword searches and checks results are non-empty:
   - `"cc cream spf"`
   - `"anti aging skincare"`
   - `"lipstick shades"`
   - `"men skincare"`
   - `"moisturizer dry skin"`
3. Runs 1 vector (hybrid) search to confirm vector field works.
4. Runs 1 semantic-ranked search to confirm semantic config works.
5. Prints pass/fail summary.

**Deliverable:** Validation report confirming index is healthy.

---

### Step 8 — Build the RAG query module

**Executor:** Claude (automated)

Create `search-site/ai_search.py` — a self-contained module exposing:

```python
def search_products(query: str, top_k: int = 5, locale: str = None) -> list[dict]
def ask(user_query: str) -> dict  # returns {"answer": ..., "sources": [...]}
```

**Implementation:**
1. `search_products()`:
   - Calls Azure AI Search with hybrid retrieval (keyword + vector + semantic reranking).
   - Optionally filters by `locale`.
   - Returns top-K results with `title`, `url`, `product_name`, `price`, `category`, `key_benefits`, `main_text` snippet.

2. `ask()`:
   - Calls `search_products()` to retrieve context.
   - Constructs a system prompt with retrieved product context.
   - Calls GPT-4.1 via the Foundry chat endpoint.
   - Returns the answer + source citations.

**Deliverable:** Working RAG module that can be imported by the FastAPI app.

---

### Step 9 — Add AI search endpoint to FastAPI app

**Executor:** Claude (automated)

Extend `search-site/app.py` to add a new API endpoint:

```python
POST /api/ai-search
Body: {"query": "...", "locale": "en"}
Response: {"answer": "...", "sources": [...]}
```

This endpoint calls `ai_search.ask()` and returns the GPT-4.1-grounded response. The existing `/api/search` endpoint (BM25/TF-IDF) remains as a fallback.

**Deliverable:** New API endpoint live on the FastAPI server.

---

### Step 10 — Add AI search UI to frontend

**Executor:** Claude (automated)

Update `search-site/static/` to add an "AI Search" mode:

1. Add a toggle/tab in the search bar: **Keyword Search** | **AI Search**.
2. When "AI Search" is selected:
   - User types a natural language question.
   - Frontend calls `POST /api/ai-search`.
   - Display the GPT-4.1 answer in a prominent answer box.
   - Below the answer, show source product cards (reusing existing card component).
3. Keep existing keyword search fully functional as the default mode.

**Deliverable:** Updated frontend with AI search capability.

---

### Step 11 — End-to-end testing

**Executor:** Claude (automated)

Run the full pipeline and verify:

| Test | Expected |
|------|----------|
| `POST /api/ai-search {"query": "best moisturizer for dry skin"}` | Returns coherent answer citing specific products |
| `POST /api/ai-search {"query": "cc cream with spf"}` | Returns CC Cream product with correct price |
| `POST /api/ai-search {"query": "what lipstick shades do you have"}` | Returns lip product results with shade info |
| `POST /api/ai-search {"query": "something not in catalog"}` | Returns graceful "not found" response |
| Existing `/api/search?q=moisturizer` still works | BM25/TF-IDF fallback unchanged |
| Frontend toggle between Keyword and AI search | Both modes render correctly |

**Deliverable:** All tests pass, documented in `3.Result/ai-search-agent_result.md`.

---

## Summary: Who Does What

| Step | Description | Executor | Blocking? |
|------|-------------|----------|-----------|
| 1 | Install Python dependencies | **Claude** | No |
| 2 | Create `.env` with credentials | **Claude** | No |
| 3 | Provision Azure AI Search resource | **You (Admin Console)** | **Yes — blocks steps 5–11** |
| 4 | Verify/deploy embedding model | **You (Admin Console)** | **Yes — blocks step 6** |
| 5 | Create search index (schema + semantic + vector) | **Claude** | No |
| 6 | Ingest 298 documents with embeddings | **Claude** | No |
| 7 | Validate index (count, sample queries) | **Claude** | No |
| 8 | Build RAG query module (`ai_search.py`) | **Claude** | No |
| 9 | Add `/api/ai-search` endpoint to FastAPI | **Claude** | No |
| 10 | Add AI search UI toggle to frontend | **Claude** | No |
| 11 | End-to-end testing | **Claude** | No |

**Your manual work: 2 steps (3 and 4). Everything else is automated.**

---

## Execution Order & Dependencies

```
Steps 1–2 (no dependencies, run first)
    │
    ├── You: Step 3 — Provision Azure AI Search ──┐
    ├── You: Step 4 — Verify embedding model ─────┤
    │                                              │
    │   (Claude waits for endpoint + key)          │
    │                                              ▼
    ├── Step 5 — Create index ─────────────► Step 6 — Ingest data
    │                                              │
    │                                              ▼
    │                                        Step 7 — Validate
    │                                              │
    ├── Step 8 — Build RAG module (can start ──────┤
    │            in parallel with 5–7)             │
    │                                              ▼
    ├── Step 9 — Add API endpoint ──────────► Step 10 — Add UI
    │                                              │
    │                                              ▼
    └──────────────────────────────────────── Step 11 — E2E test
```

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `.env` | Create — Foundry + Search credentials |
| `.gitignore` | Update — add `.env` |
| `search-site/requirements.txt` | Update — add Azure SDKs |
| `scripts/create_index.py` | Create — index definition + creation |
| `scripts/ingest_data.py` | Create — data transform + embedding + upload |
| `scripts/validate_index.py` | Create — index health check |
| `search-site/ai_search.py` | Create — RAG query module |
| `search-site/app.py` | Update — add `/api/ai-search` endpoint |
| `search-site/static/index.html` | Update — add AI search toggle |
| `search-site/static/app.js` | Update — add AI search interaction |
| `search-site/static/style.css` | Update — style AI answer box |
| `3.Result/ai-search-agent_result.md` | Create — test results |
