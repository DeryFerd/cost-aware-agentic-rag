# STRUCTURE.md — Arsitektur Final

> Peta lengkap seluruh sistem: frontend, backend, API, data flow, dan koneksi antar modul.

---

## 1. Directory Tree

```
cost-aware-agentic-rag/
├── .env                          # Ollama Cloud API key, Redis, Langfuse config
├── Dockerfile                    # Python 3.11-slim, port 8001
├── docker-compose.yml            # api, frontend, postgres, redis, celery
├── pyproject.toml                # Project metadata + deps
├── requirements.txt              # Pinned dependencies
│
├── api/
│   ├── main.py                   # FastAPI app — 30+ endpoints, Jinja2, SSE streaming
│   └── models.py                 # Pydantic request/response schemas
│
├── src/
│   ├── config.py                 # Central Settings (pydantic-settings)
│   │
│   ├── agents/                   # 🧠 AGENT ORCHESTRATION
│   │   ├── graph.py              #   LangGraph StateGraph (classify→retrieve→generate→reflect)
│   │   ├── memory.py             #   ConversationMemory (per-session, in-memory)
│   │   └── guardrails.py         #   InputGuardrails + OutputGuardrails
│   │
│   ├── generation/               # 🤖 LLM INFERENCE
│   │   ├── llm_client.py         #   OllamaClient (gemma3:4b, gemma3:27b, minimax-m3:cloud)
│   │   ├── cost_tracker.py       #   CostTracker (JSONL persistence)
│   │   └── prompts.py            #   System prompt, router prompt, etc.
│   │
│   ├── retrieval/                # 🔍 RETRIEVAL ENGINE
│   │   ├── vector_store.py       #   ChromaDB + bge-small-en-v1.5 (384d)
│   │   ├── bm25_index.py         #   BM25Okapi (pickle persistence)
│   │   ├── hybrid.py             #   HybridRetriever (vector + BM25 + RRF + cross-encoder)
│   │   ├── fusion.py             #   RRF algorithm: score = Σ 1/(k + rank_i)
│   │   └── reranker.py           #   CrossEncoderReranker (ms-marco-MiniLM-L-6-v2)
│   │
│   ├── ingestion/                # 📄 DOCUMENT INGESTION
│   │   ├── pipeline.py           #   run_ingestion (download→parse→embed→index)
│   │   ├── downloader.py         #   SEC EDGAR 10-K downloader
│   │   ├── parser.py             #   Docling-based chunk_document
│   │   ├── chunker.py            #   SemanticChunker (parent-child, overlap)
│   │   └── upload_handler.py     #   File upload: validate→save→process
│   │
│   ├── ml/                       # 📊 ML & ANALYTICS
│   │   ├── routing.py            #   CostAwareRouter (TF-IDF + LogisticRegression)
│   │   ├── query_processor.py    #   QueryProcessor (rewrite, HyDE, multi-query)
│   │   ├── feedback.py           #   Feedback storage (JSONL)
│   │   ├── cost_analytics.py     #   CostAnalytics (model comparison, trends)
│   │   ├── export.py             #   QueryExporter (PDF via fpdf2, CSV)
│   │   ├── suggestions.py        #   QuerySuggestion (pattern + document-based)
│   │   ├── anomaly.py            #   AnomalyDetector (cost, latency, routing)
│   │   └── evaluation.py         #   MLEvaluator (heuristic scoring)
│   │
│   ├── eval/                     # 🧪 EVALUATION
│   │   ├── pipeline.py           #   EvalPipeline (retrieval + generation metrics)
│   │   ├── llm_judge.py          #   LLMJudge (minimax-m3:cloud as judge)
│   │   ├── golden_set.py         #   55 golden Q&A pairs
│   │   ├── ragas_eval.py         #   RAGAS evaluator (optional lib)
│   │   └── retrieval_metrics.py  #   NDCG@10, MRR, Recall@K, Precision@K
│   │
│   ├── database/                 # 💾 STORAGE
│   │   ├── cache.py              #   Redis wrapper (optional)
│   │   ├── admin_auth.py         #   File-based admin auth (users.json)
│   │   └── models.py             #   SQLAlchemy models (NOT USED)
│   │
│   ├── knowledge/                # 🕸️ KNOWLEDGE GRAPH
│   │   └── graph.py              #   FinancialKnowledgeGraph (NetworkX)
│   │
│   ├── multimodal/               # 🖼️ MULTIMODAL
│   │   ├── activator.py          #   CLIP embeddings + image-text similarity
│   │   ├── vision.py             #   VisionAnalyzer (gemma3:27b vision)
│   │   ├── tables.py             #   Table extraction (regex-based)
│   │   └── images.py             #   PDF image extraction (Docling)
│   │
│   ├── tasks/                    # ⚙️ BACKGROUND TASKS
│   │   └── celery_app.py         #   Celery tasks (NOT TRIGGERED yet)
│   │
│   └── observability/            # 📈 OBSERVABILITY
│       └── langfuse.py           #   Langfuse wrapper (optional)
│
├── web/templates/                # 🎨 JINJA2 FRONTEND (7 pages)
│   ├── index.html                #   Landing page
│   ├── app.html                  #   Main chat interface (SSE streaming)
│   ├── upload.html               #   File upload (drag-and-drop)
│   ├── documents.html            #   Document browser
│   ├── analytics.html            #   Cost analytics dashboard
│   ├── comparison.html           #   Model comparison
│   └── admin.html                #   Admin panel
│
├── frontend/                     # 🎨 NEXT.JS FRONTEND (Docker, 3 pages)
│   └── src/app/
│       ├── page.tsx              #   Chat (hardcodes localhost:8001)
│       ├── documents/page.tsx    #   Documents
│       └── analytics/page.tsx    #   Analytics
│
├── scripts/                      # 🔧 CLI SCRIPTS
│   ├── ingest.py                 #   Run ingestion
│   ├── eval_ragas.py             #   RAGAS evaluation
│   ├── eval_llm_judge.py         #   LLM-as-judge evaluation
│   └── create_samples.py         #   Generate sample 10-K files
│
├── tests/                        # ✅ TESTS
│   ├── conftest.py               #   Pytest fixtures (mock LLM, Redis)
│   └── test_comprehensive.py     #   93 tests
│
└── data/                         # 📁 DATA (all file-based)
    ├── raw/{TICKER}/{YEAR}/      #   SEC 10-K raw .txt files
    ├── processed/                #   Parsed chunks
    ├── indexes/
    │   ├── chroma/               #   ChromaDB vector store
    │   └── bm25.pkl              #   BM25 index
    ├── eval/                     #   Evaluation results JSON
    ├── feedback/                 #   User feedback (JSONL daily)
    ├── exports/                  #   PDF/CSV exports
    ├── uploads/                  #   Uploaded files
    ├── admin/users.json          #   Admin credentials (SHA-256)
    └── queries/                  #   Query history
```

---

## 2. Koneksi Antar Modul (Import Graph)

### api/main.py → Module apa saja yang dipanggil

```
api/main.py
├── src/config.py                 ← settings (ALL config)
├── src/agents/graph.py           ← LangGraphOrchestrator
├── src/agents/memory.py          ← ConversationMemory
├── src/agents/guardrails.py      ← InputGuardrails, OutputGuardrails
├── src/generation/cost_tracker.py← CostTracker
├── src/generation/llm_client.py  ← OllamaClient (di streaming endpoint)
├── src/retrieval/hybrid.py       ← HybridRetriever
├── src/ml/routing.py             ← CostAwareRouter
├── src/ml/query_processor.py     ← QueryProcessor
├── src/ml/feedback.py            ← store_feedback, get_feedback_stats
├── src/ml/cost_analytics.py      ← CostAnalytics
├── src/ml/export.py              ← QueryExporter
├── src/ml/anomaly.py             ← AnomalyDetector
├── src/ml/suggestions.py         ← QuerySuggestion
├── src/database/cache.py         ← CacheManager
├── src/database/admin_auth.py    ← authenticate_user, create_session
├── src/knowledge/graph.py        ← FinancialKnowledgeGraph
├── src/eval/pipeline.py          ← EvalPipeline
└── src/ingestion/upload_handler.py ← validate_upload, save_upload, process_upload
```

### src/agents/graph.py → Agent internals

```
src/agents/graph.py (LangGraphOrchestrator)
├── src/generation/llm_client.py  ← OllamaClient (chat + chat_stream)
├── src/generation/prompts.py     ← SYSTEM_PROMPT, ROUTER_PROMPT, etc.
├── src/retrieval/hybrid.py       ← HybridRetriever.retrieve()
├── src/agents/memory.py          ← ConversationMemory
├── src/agents/guardrails.py      ← InputGuardrails, OutputGuardrails
└── src/ml/routing.py             ← CostAwareRouter
```

### src/retrieval/hybrid.py → Retrieval stack

```
src/retrieval/hybrid.py (HybridRetriever)
├── src/retrieval/vector_store.py ← ChromaDB semantic search
├── src/retrieval/bm25_index.py   ← BM25Okapi keyword search
├── src/retrieval/fusion.py       ← reciprocal_rank_fusion (RRF)
└── src/retrieval/reranker.py     ← CrossEncoderReranker
```

### src/ingestion/ → Document processing pipeline

```
src/ingestion/pipeline.py
├── src/ingestion/downloader.py   ← SEC EDGAR download
├── src/ingestion/parser.py       ← Docling chunk_document
├── src/retrieval/vector_store.py ← ChromaDB add_documents
└── src/retrieval/bm25_index.py   ← BM25 add_documents + save
```

---

## 3. API Endpoints (30+ endpoints)

### Core Query

| Method | Path | Handler | Module | Fungsi |
|--------|------|---------|--------|--------|
| POST | `/query` | `query()` | LangGraphOrchestrator | Sync query (full graph) |
| POST | `/query/stream` | `query_stream()` | HybridRetriever, QueryProcessor, OllamaClient | SSE streaming |

### Ingestion & Upload

| Method | Path | Handler | Module | Fungsi |
|--------|------|---------|--------|--------|
| POST | `/upload` | `upload_document()` | upload_handler | Upload PDF |
| GET | `/upload/{doc_id}/status` | `get_upload_status()` | upload_handler | Status upload |
| DELETE | `/upload/{doc_id}` | `delete_document()` | upload_handler | Hapus dokumen |

### Documents

| Method | Path | Handler | Module | Fungsi |
|--------|------|---------|--------|--------|
| GET | `/documents/list` | `list_documents()` | VectorStore, BM25Index | List semua dokumen |
| GET | `/documents/search` | `search_documents()` | VectorStore | Cari dokumen |
| GET | `/documents/stats` | `get_document_stats()` | VectorStore, BM25Index | Statistik chunks |

### Feedback & Suggestions

| Method | Path | Handler | Module | Fungsi |
|--------|------|---------|--------|--------|
| POST | `/feedback` | `submit_feedback()` | ml/feedback | Simpan feedback |
| GET | `/feedback/stats` | `get_feedback_stats()` | ml/feedback | Statistik feedback |
| GET | `/feedback/recent` | `get_recent_feedback()` | ml/feedback | Recent feedback |
| GET | `/suggestions` | `get_suggestions()` | QuerySuggestion | Query suggestions |
| GET | `/suggestions/document-based` | `get_document_based_suggestions()` | QuerySuggestion | Doc-based suggestions |

### Cost & Analytics

| Method | Path | Handler | Module | Fungsi |
|--------|------|---------|--------|--------|
| GET | `/cost/summary` | `get_cost_summary()` | CostTracker | Ringkasan biaya |
| GET | `/cost/history` | `get_cost_history()` | CostTracker | Riwayat biaya |
| GET | `/analytics/costs` | `get_cost_analytics()` | CostAnalytics | Analisis biaya |
| GET | `/analytics/trends` | `get_cost_trends()` | CostAnalytics | Tren biaya harian |
| GET | `/analytics/model-comparison` | `get_model_comparison()` | CostAnalytics | Perbandingan model |
| GET | `/analytics/optimization` | `get_optimization_suggestions()` | CostAnalytics | Saran optimasi |
| GET | `/analytics/breakdown` | `get_cost_breakdown()` | CostAnalytics | Breakdown biaya |
| GET | `/analytics/anomalies` | `get_anomalies()` | AnomalyDetector | Deteksi anomali |
| POST | `/analytics/export/csv` | `export_csv()` | QueryExporter | Export CSV |
| POST | `/analytics/export/pdf` | `export_pdf()` | QueryExporter | Export PDF |
| GET | `/analytics/retention` | `get_data_retention_info()` | CostAnalytics | Info retensi data |

### Evaluation & Knowledge Graph

| Method | Path | Handler | Module | Fungsi |
|--------|------|---------|--------|--------|
| POST | `/eval/run` | `run_evaluation()` | EvalPipeline | Jalankan evaluasi |
| GET | `/eval/results` | `get_evaluation_results()` | eval | Hasil evaluasi |
| GET | `/eval/export` | `export_evaluation()` | eval | Export evaluasi |
| POST | `/knowledge/graph` | `query_knowledge_graph()` | FinancialKnowledgeGraph | Query knowledge graph |
| GET | `/knowledge/graph/stats` | `get_knowledge_graph_stats()` | FinancialKnowledgeGraph | Statistik graph |

### Admin

| Method | Path | Handler | Module | Fungsi |
|--------|------|---------|--------|--------|
| POST | `/admin/login` | `admin_login()` | admin_auth | Login admin |
| GET | `/admin/system` | `get_system_status()` | VectorStore, BM25Index | Status sistem |
| GET | `/admin/users` | `list_users()` | admin_auth | List users |
| POST | `/admin/users` | `create_user()` | admin_auth | Buat user |
| DELETE | `/admin/users/{username}` | `delete_user()` | admin_auth | Hapus user |
| GET | `/admin/sessions` | `get_sessions()` | admin_auth | Active sessions |
| DELETE | `/admin/sessions/{session_id}` | `revoke_session()` | admin_auth | Revoke session |
| POST | `/admin/clear-cache` | `clear_cache()` | CacheManager | Clear cache |
| GET | `/admin/cache/stats` | `get_cache_stats()` | CacheManager | Stats cache |

### Other

| Method | Path | Handler | Module | Fungsi |
|--------|------|---------|--------|--------|
| GET | `/health` | `health_check()` | VectorStore, BM25Index | Health check |
| POST | `/compare` | `compare_models()` | OllamaClient | Bandingkan model |
| POST | `/ingest/run` | `run_ingestion()` | pipeline | Trigger ingestion |

---

## 4. Frontend → API Mapping

### A. Jinja2 Templates (Server-rendered, 7 pages)

| Halaman | Template | JS AJAX Endpoints |
|---------|----------|-------------------|
| Landing | `index.html` | `GET /health` (SSE polling) |
| **Chat** | `app.html` | `POST /query/stream` (SSE), `GET /suggestions`, `POST /feedback`, `GET /documents/list` |
| Upload | `upload.html` | `POST /upload`, `GET /upload/{doc_id}/status`, `GET /documents/list` |
| Documents | `documents.html` | `GET /documents/list`, `GET /documents/stats` |
| Analytics | `analytics.html` | `GET /analytics/*`, `POST /analytics/export/*` |
| Comparison | `comparison.html` | `POST /compare`, `GET /comparison` |
| Admin | `admin.html` | `POST /admin/login`, `GET /admin/*`, `POST /admin/*` |

### B. Next.js Frontend (Docker, 3 pages only)

| Halaman | File | API Endpoints |
|---------|------|---------------|
| Chat | `frontend/src/app/page.tsx` | `POST http://localhost:8001/query/stream` |
| Documents | `frontend/src/app/documents/page.tsx` | `GET http://127.0.0.1:8001/documents` |
| Analytics | `frontend/src/app/analytics/page.tsx` | `GET /health`, `GET /cost/summary`, `GET /documents` |

> ⚠️ Next.js frontend **hardcodes** `localhost:8001` — hanya untuk dev/docker.

### C. Streamlit Dashboard (opsional)

| File | API Endpoints |
|------|---------------|
| `dashboard/app.py` | `GET http://localhost:8000/health`, `POST /query`, `GET /cost/summary` |

---

## 5. Data Flow

### 🔄 Query Flow (Primary)

```
User ketik query
    │
    ▼
┌─────────────────────────────┐
│  api/main.py                │
│  POST /query/stream         │
└─────────┬───────────────────┘
          │
    ┌─────▼──────────────────┐
    │ InputGuardrails        │ ← PII check, length, sanitization
    └─────┬──────────────────┘
          │
    ┌─────▼──────────────────┐
    │ CacheManager (Redis)   │ ← Check cache (optional)
    └─────┬──────────────────┘
          │ (miss)
    ┌─────▼──────────────────┐
    │ QueryProcessor         │ ← Rewrite, HyDE, multi-query expansion
    │ (query_processor.py)   │
    └─────┬──────────────────┘
          │
    ┌─────▼──────────────────┐
    │ CostAwareRouter        │ ← TF-IDF classifier → gemma3:4b / gemma3:27b
    │ (routing.py)           │
    └─────┬──────────────────┘
          │
    ┌─────▼──────────────────┐
    │ HybridRetriever        │
    │   ├─ VectorStore       │ ← ChromaDB semantic search (bge-small-en-v1.5)
    │   ├─ BM25Index         │ ← BM25Okapi keyword search
    │   ├─ RRF Fusion        │ ← score = Σ 1/(k + rank_i), k=60
    │   └─ CrossEncoder      │ ← ms-marco-MiniLM-L-6-v2 reranking
    └─────┬──────────────────┘
          │
    ┌─────▼──────────────────┐
    │ OllamaClient           │ ← LLM generation (gemma3:4b/27b)
    │ chat_stream()          │
    └─────┬──────────────────┘
          │
    ┌─────▼──────────────────┐
    │ OutputGuardrails       │ ← Grounding check, hallucination detect
    └─────┬──────────────────┘
          │
    ┌─────▼──────────────────┐
    │ CostTracker            │ ← Log cost, latency, tokens
    └─────┬──────────────────┘
          │
    ▼
 SSE stream → Frontend
```

### 📥 Ingestion Flow

```
POST /ingest/run  atau  scripts/ingest.py
    │
    ▼
┌─────────────────────┐
│ downloader.py       │ ← SEC EDGAR API → data/raw/{TICKER}/{YEAR}/*.txt
└─────┬───────────────┘
      │
┌─────▼───────────────┐
│ parser.py           │ ← Docling parse → chunks with metadata
│ (chunk_document)    │
└─────┬───────────────┘
      │
┌─────▼───────────────┐
│ VectorStore         │ ← ChromaDB add_documents (embed + index)
│ (vector_store.py)   │   → data/indexes/chroma/
└─────┬───────────────┘
      │
┌─────▼───────────────┐
│ BM25Index           │ ← BM25 add_documents + save
│ (bm25_index.py)     │   → data/indexes/bm25.pkl
└─────────────────────┘
```

### 📤 Upload Flow

```
User upload PDF (drag-and-drop)
    │
    ▼
┌─────────────────────┐
│ validate_upload()   │ ← Check file type, size (max 100MB)
└─────┬───────────────┘
      │
┌─────▼───────────────┐
│ save_upload()       │ ← Save ke data/uploads/
└─────┬───────────────┘
      │
┌─────▼───────────────┐
│ process_upload()    │ ← chunk_document → VectorStore → BM25Index
└─────────────────────┘
```

### 🧪 Evaluation Flow

```
scripts/eval_ragas.py
scripts/eval_llm_judge.py
POST /eval/run
    │
    ▼
┌─────────────────────┐
│ LangGraphOrchestrator│ ← Jalankan query
└─────┬───────────────┘
      │
┌─────▼───────────────┐
│ EvalPipeline        │ ← Hitung metrics:
│ (eval/pipeline.py)  │   - retrieval_precision
│                     │   - retrieval_recall
│                     │   - context_relevance
│                     │   - answer_faithfulness
│                     │   - answer_relevance
└─────┬───────────────┘
      │
┌─────▼───────────────┐
│ CIGating            │ ← Pass/fail threshold check
└─────────────────────┘
```

---

## 6. External Services

| Service | Config | Digunakan Oleh |
|---------|--------|----------------|
| **Ollama Cloud** | `OLLAMA_BASE_URL`, `OLLAMA_API_KEY` | LLMClient — gemma3:4b, gemma3:27b, minimax-m3:cloud |
| **SEC EDGAR** | Hardcoded URLs | downloader.py — fetch 10-K filings |
| **Redis** | `REDIS_URL` (optional) | CacheManager — query cache, rate limiting |
| **PostgreSQL** | `DATABASE_URL` (optional) | SQLAlchemy models — **TIDAK DIPAKAI** |
| **Langfuse** | `LANGFUSE_*` (optional) | Observability — tracing, eval |

---

## 7. Model Stack

| Model | Ukuran | Lokasi | Fungsi |
|-------|--------|--------|--------|
| `BAAI/bge-small-en-v1.5` | 384d | Local | Embeddings (ChromaDB) |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | 22M | Local | Reranking retrieval results |
| `gemma3:4b` | 4B | Ollama Cloud | Simple queries (cost: $0.075/1M tokens) |
| `gemma3:27b` | 27B | Ollama Cloud | Complex queries + vision (cost: $0.30/1M tokens) |
| `minimax-m3:cloud` | Large | Ollama Cloud | LLM-as-Judge evaluation |
| `TF-IDF + LogisticRegression` | - | Local (sklearn) | Query complexity classification |

---

## 8. Arsitektur Visual

```
┌──────────────────────────────────────────────────────────────┐
│                        FRONTEND                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Jinja2 UI   │  │  Next.js UI  │  │  Streamlit   │       │
│  │  (7 pages)   │  │  (3 pages)   │  │  (1 page)    │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
└─────────┼─────────────────┼─────────────────┼────────────────┘
          │ SSE/JSON        │ HTTP            │ HTTP
          ▼                 ▼                 ▼
┌──────────────────────────────────────────────────────────────┐
│                     API LAYER (FastAPI)                        │
│                    api/main.py (port 8001)                    │
│                                                              │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐  │
│  │ /query  │ │ /upload  │ │ /admin   │ │ /analytics/*    │  │
│  │ /stream │ │ /docs    │ │ /users   │ │ /feedback/*     │  │
│  └────┬────┘ └────┬─────┘ └────┬─────┘ │ /eval/*         │  │
└───────┼───────────┼────────────┼────────┼─────────────────┘
        │           │            │        │
┌───────▼───────────▼────────────▼────────▼─────────────────┐
│                    BACKEND MODULES                           │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │  agents/         │  │  retrieval/      │                  │
│  │  graph.py        │  │  hybrid.py       │                  │
│  │  memory.py       │  │  vector_store.py │                  │
│  │  guardrails.py   │  │  bm25_index.py   │                  │
│  └────────┬────────┘  │  fusion.py       │                  │
│           │            │  reranker.py     │                  │
│           │            └────────┬────────┘                  │
│           │                     │                            │
│  ┌────────▼─────────────────────▼────────┐                  │
│  │           generation/                  │                  │
│  │  llm_client.py (OllamaCloud)          │                  │
│  │  cost_tracker.py (JSONL)              │                  │
│  └───────────────────────────────────────┘                  │
│                                                             │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌────────────┐  │
│  │  ml/       │ │  eval/     │ │  ingest/   │ │ knowledge/ │  │
│  │  routing   │ │  pipeline  │ │  parser    │ │ graph.py   │  │
│  │  query_proc│ │  llm_judge │ │  chunker   │ └────────────┘  │
│  │  feedback  │ │  ragas     │ │  upload    │                 │
│  │  analytics │ │  retrieval │ │  download  │ ┌────────────┐  │
│  │  export    │ │  golden_set│ └───────────┘ │multimodal/  │  │
│  │  anomaly   │ └───────────┘               │ activator   │  │
│  │  suggest   │                             │ vision      │  │
│  └───────────┘                             └────────────┘  │
└─────────────────────────────────────────────────────────────┘
          │                                    │
┌─────────▼────────────────────────────────────▼──────────┐
│                    STORAGE (File-based)                   │
│                                                          │
│  data/raw/{TICKER}/{YEAR}/     ← SEC 10-K .txt files   │
│  data/indexes/chroma/          ← Vector embeddings      │
│  data/indexes/bm25.pkl         ← BM25 inverted index    │
│  data/feedback/*.jsonl         ← User feedback          │
│  data/exports/                 ← PDF/CSV exports        │
│  data/uploads/                 ← Uploaded PDFs          │
│  data/admin/users.json         ← Admin credentials      │
│  data/eval/*.json              ← Evaluation results     │
│                                                          │
│  Redis (optional)              ← Query cache            │
│  PostgreSQL (NOT USED)         ← —                      │
└──────────────────────────────────────────────────────────┘
```

---

## 9. Catatan Penting

### Dual Frontend
- **Jinja2** (7 halaman): Full fitur — Chat, Upload, Documents, Analytics, Comparison, Admin, Landing
- **Next.js** (3 halaman): Hanya Chat, Documents, Analytics — hardcoded `localhost:8001`
- **Streamlit** (1 halaman): Dashboard sederhana

### File-based Persistence
Semua data disimpan di file (JSONL, pickle, JSON, txt). Tidak ada dependency ke database. Redis optional.

### Cost-Aware Routing
Classifier sklearn (TF-IDF + LogisticRegression) menentukan query sederhana vs kompleks:
- **Sederhana** → gemma3:4b (murah, cepat)
- **Kompleks** → gemma3:27b (mahal, lebih baik + vision)

### LangGraph State Graph
4 node: `classify → retrieve → generate → reflect`. Reflect bisa loop balik ke retrieve jika kualitas rendah (bounded).

### Dead Code
- `src/database/models.py` — SQLAlchemy models, tidak dipakai
- `src/tasks/celery_app.py` — Celery tasks, belum di-trigger
- `scripts/evaluate.py`, `scripts/evaluate_ml.py` — Import `AgenticOrchestrator` (stale, class asli = `LangGraphOrchestrator`)
