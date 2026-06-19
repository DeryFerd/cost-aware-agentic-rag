# STRUCTURE.md — Architecture Map

> Complete system map: frontend, backend, API, data flow, and module connections.

---

## 1. Directory Tree

```
cost-aware-agentic-rag/
├── .env                          # Ollama Cloud API key, Redis, Langfuse config
├── .github/workflows/ci.yml      # CI: lint → test → eval → docker
├── Dockerfile                    # Python 3.11-slim, port 8001
├── docker-compose.yml            # api + redis
├── pyproject.toml                # Project metadata + ruff config
├── requirements.txt              # Pinned dependencies
├── STRUCTURE.md                  # This file
├── PROGRESS.md                   # Development progress
├── README.md                     # Project docs with ADRs
│
├── api/
│   ├── main.py                   # FastAPI app (thin, router registration)
│   ├── models.py                 # Pydantic request/response schemas
│   └── routes/
│       ├── query.py              #   /query, /query/stream, /query/structured
│       ├── upload.py             #   /upload CRUD
│       ├── documents.py          #   /documents, /conversation
│       ├── feedback.py           #   /feedback, /suggestions
│       ├── analytics.py          #   /analytics, /cost, /latency, /prompts
│       ├── admin.py              #   /admin (auth required), /tenants (auth required)
│       ├── knowledge.py          #   /knowledge, /eval
│       └── compare.py            #   /compare/years, /compare/companies
│
├── src/
│   ├── config.py                 # Central Settings (pydantic-settings)
│   │
│   ├── agents/                   # Agent orchestration
│   │   ├── graph.py              #   LangGraph StateGraph + LangGraphOrchestrator
│   │   │                         #   (classify→retrieve→generate→reflect, tenant filtering, cost accumulation)
│   │   ├── memory.py             #   ConversationMemory (per-session, in-memory)
│   │   ├── guardrails.py         #   InputGuardrails + OutputGuardrails
│   │   └── compare.py            #   FilingComparator (year-over-year, cross-company)
│   │
│   ├── generation/               # LLM inference
│   │   ├── llm_client.py         #   OllamaClient (gemma3:4b, gemma3:27b, minimax-m3:cloud)
│   │   ├── cost_tracker.py       #   CostTracker (JSONL persistence, per-query cost)
│   │   ├── prompts.py            #   System/router/summarize/compare/cite/validate prompts
│   │   ├── prompt_registry.py    #   Versioned prompts (JSON in data/prompts/)
│   │   └── structured_output.py  #   Pydantic schemas (QueryAnswer, ComparisonResult)
│   │
│   ├── retrieval/                # Retrieval engine
│   │   ├── vector_store.py       #   ChromaDB + bge-small-en-v1.5 (384d)
│   │   ├── bm25_index.py         #   BM25Okapi (stemming + stopwords)
│   │   ├── hybrid.py             #   HybridRetriever (vector + BM25 + RRF + cross-encoder)
│   │   ├── fusion.py             #   RRF algorithm: score = Σ 1/(k + rank_i), k=60
│   │   ├── reranker.py           #   CrossEncoderReranker (ms-marco-MiniLM-L-6-v2)
│   │   ├── rbac.py               #   Document-level access control
│   │   └── tenant_filter.py      #   Tenant-based retrieval filtering
│   │
│   ├── ingestion/                # Document ingestion
│   │   ├── pipeline.py           #   run_ingestion (download→parse→embed→index)
│   │   ├── downloader.py         #   SEC EDGAR 10-K downloader
│   │   ├── parser.py             #   Docling-based chunk_document
│   │   ├── chunker.py            #   SemanticChunker (parent-child, overlap)
│   │   ├── upload_handler.py     #   File upload: validate→save→process
│   │   └── async_pipeline.py     #   Async document processing
│   │
│   ├── ml/                       # ML & analytics
│   │   ├── routing.py            #   CostAwareRouter (TF-IDF + LogisticRegression, 110 examples)
│   │   ├── query_processor.py    #   QueryProcessor (rewrite, HyDE, multi-query)
│   │   ├── feedback.py           #   Feedback storage (JSONL)
│   │   ├── cost_analytics.py     #   CostAnalytics (model comparison, trends)
│   │   ├── cost_optimizer.py     #   Token budgets, savings report, cache hits
│   │   ├── export.py             #   QueryExporter (PDF via fpdf2, CSV)
│   │   ├── suggestions.py        #   QuerySuggestion (pattern + document-based)
│   │   ├── anomaly.py            #   AnomalyDetector (cost, latency, routing)
│   │   ├── latency_tracker.py    #   LatencyTracker (p50/p95/p99 per component)
│   │   ├── ab_testing.py         #   Model A/B testing (probabilistic routing)
│   │   └── evaluation.py         #   MLEvaluator (heuristic scoring)
│   │
│   ├── eval/                     # Evaluation
│   │   ├── pipeline.py           #   EvalPipeline + CIGating + EvalStorage
│   │   ├── harness.py            #   Unified eval harness (golden set + judge + failure buckets)
│   │   ├── llm_judge.py          #   LLMJudge (minimax-m3:cloud as judge)
│   │   ├── golden_set.py         #   Golden Q&A pairs (Python module)
│   │   ├── ragas_eval.py         #   RAGAS evaluator (optional lib)
│   │   ├── retrieval_metrics.py  #   NDCG@10, MRR, Recall@K, Precision@K, Hit Rate
│   │   └── prompt_regression.py  #   Prompt regression testing
│   │
│   ├── database/                 # Storage
│   │   ├── cache.py              #   Redis wrapper (optional)
│   │   ├── semantic_cache.py     #   Semantic cache (cosine similarity 0.92)
│   │   ├── admin_auth.py         #   File-based admin auth (bcrypt, require_admin dependency)
│   │   ├── tenants.py            #   Multi-tenant management (CRUD, budgets, usage)
│   │   ├── audit.py              #   Audit logging (JSONL trail for admin/auth/query)
│   │   └── models.py             #   SQLAlchemy models (DEAD CODE)
│   │
│   ├── knowledge/                # Knowledge graph
│   │   └── graph.py              #   FinancialKnowledgeGraph (NetworkX + SpaCy NER + LLM)
│   │
│   ├── multimodal/               # Multimodal
│   │   ├── activator.py          #   CLIP embeddings + Docling table extraction
│   │   ├── vision.py             #   VisionAnalyzer (gemma3:27b)
│   │   ├── tables.py             #   Table extraction (regex-based)
│   │   └── images.py             #   PDF image extraction
│   │
│   ├── tasks/                    # Background tasks
│   │   └── celery_app.py         #   Celery tasks (DEAD CODE)
│   │
│   └── observability/            # Observability
│       ├── langfuse.py           #   Langfuse wrapper (flat traces)
│       └── tracing.py            #   OpenTelemetry (TracerProvider + OTLP + @instrument)
│
├── web/templates/                # Jinja2 frontend (9 pages)
│   ├── index.html                #   Landing page (8-card grid)
│   ├── app.html                  #   Chat dashboard (SSE streaming)
│   ├── upload.html               #   Document upload (drag-and-drop)
│   ├── documents.html            #   Document browser
│   ├── analytics.html            #   Analytics dashboard
│   ├── comparison.html           #   Model comparison dashboard
│   ├── latency.html              #   Latency dashboard (p50/p95/p99)
│   ├── cost_optimization.html    #   Cost optimization dashboard
│   └── admin.html                #   Admin panel (auth, users, tenants, cache)
│
├── scripts/                      # CLI scripts
│   ├── ingest.py                 #   Run ingestion
│   ├── register_prompts.py       #   Register versioned prompts
│   ├── eval_ragas.py             #   RAGAS evaluation
│   ├── eval_llm_judge.py         #   LLM-as-judge evaluation
│   ├── evaluate.py               #   Evaluation (FIXED: uses LangGraphOrchestrator)
│   ├── evaluate_ml.py            #   ML evaluation (FIXED: uses CostAwareRouter)
│   └── load_test.py              #   Load test (concurrent users, p50/p95/p99)
│
├── tests/                        # Tests (237 total)
│   ├── conftest.py               #   Pytest fixtures (mock LLM, Redis)
│   ├── test_comprehensive.py     #   167 unit tests
│   └── test_integration.py       #   70 integration tests
│
└── data/                         # All file-based storage
    ├── raw/{TICKER}/{YEAR}/      #   SEC 10-K raw .txt files
    ├── processed/                #   Parsed chunks
    ├── indexes/
    │   ├── chroma/               #   ChromaDB vector store
    │   └── bm25.pkl              #   BM25 index
    ├── eval/
    │   ├── golden_set.json        #   20 eval entries with source doc IDs
    │   ├── harness_results.json   #   Eval harness results
    │   ├── llm_judge_results.json #   LLM-as-judge results
    │   └── retrieval_metrics.json #   Retrieval metrics
    ├── prompts/                  #   Versioned prompts (JSON)
    ├── training/routing_data.json #   110 routing training examples
    ├── feedback/                 #   User feedback (JSONL daily)
    ├── exports/                  #   PDF/CSV exports
    ├── uploads/                  #   Uploaded files
    ├── admin/users.json          #   Admin credentials (bcrypt)
    ├── tenants/                  #   Tenant data
    ├── audit/audit.jsonl         #   Audit trail
    ├── metrics/                  #   Latency, A/B test, load test logs
    └── cost_log.jsonl            #   Per-query cost records
```

---

## 2. Module Connection Graph

### api/main.py → All routers

```
api/main.py
├── api/routes/query.py           ← POST /query, /query/stream, /query/structured
├── api/routes/upload.py          ← POST /upload, GET /uploads
├── api/routes/documents.py       ← GET /documents, /conversation/*
├── api/routes/feedback.py        ← POST /feedback, GET /suggestions
├── api/routes/analytics.py       ← GET /analytics/*, /cost/*, /latency/*, /prompts/*
├── api/routes/admin.py           ← POST /admin/login, CRUD users/tenants (auth required)
├── api/routes/knowledge.py       ← GET /knowledge/*, POST /eval/*
├── api/routes/compare.py         ← POST /compare/years, /compare/companies
└── src/observability/tracing.py  ← setup_tracing() on startup
```

### src/agents/graph.py → Agent internals

```
src/agents/graph.py (LangGraphOrchestrator)
├── src/generation/llm_client.py  ← OllamaClient (chat + chat_stream)
├── src/generation/prompts.py     ← SYSTEM_PROMPT, ROUTER_PROMPT, etc.
├── src/retrieval/hybrid.py       ← HybridRetriever.retrieve()
├── src/agents/memory.py          ← ConversationMemory
├── src/agents/guardrails.py      ← InputGuardrails, OutputGuardrails
├── src/ml/routing.py             ← CostAwareRouter
├── src/database/tenants.py       ← TenantManager (for tenant filtering)
└── src/observability/tracing.py  ← @instrument decorator on nodes
```

### src/retrieval/hybrid.py → Retrieval stack

```
src/retrieval/hybrid.py (HybridRetriever)
├── src/retrieval/vector_store.py ← ChromaDB semantic search
├── src/retrieval/bm25_index.py   ← BM25Okapi keyword search
├── src/retrieval/fusion.py       ← reciprocal_rank_fusion (RRF)
├── src/retrieval/reranker.py     ← CrossEncoderReranker
└── src/observability/tracing.py  ← @instrument decorator
```

### src/ingestion/ → Document processing pipeline

```
src/ingestion/pipeline.py
├── src/ingestion/downloader.py   ← SEC EDGAR download
├── src/ingestion/parser.py       ← Docling chunk_document
├── src/retrieval/vector_store.py ← ChromaDB add_documents
└── src/retrieval/bm25_index.py   ← BM25 add_documents + save
```

### src/eval/harness.py → Unified eval

```
src/eval/harness.py
├── src/eval/llm_judge.py         ← LLMJudge (structured JSON output)
├── src/eval/retrieval_metrics.py ← NDCG, MRR, Recall, Precision
├── src/agents/graph.py           ← LangGraphOrchestrator.run()
├── src/generation/cost_tracker.py← CostTracker (per-query cost)
└── src/ml/latency_tracker.py     ← LatencyTracker (p50/p95/p99)
```

---

## 3. API Endpoints (45+)

### Core Query (auth optional, tenant optional)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/query` | — | Sync query (full pipeline) |
| POST | `/query/stream` | — | SSE streaming response |
| POST | `/query/structured` | — | Structured output (Pydantic) |

### Ingestion & Upload

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/upload` | — | Upload PDF for indexing |
| GET | `/upload/{doc_id}/status` | — | Check upload status |
| DELETE | `/upload/{doc_id}` | — | Delete document |
| GET | `/uploads` | — | List all uploads |

### Documents & Conversation

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/documents` | — | List indexed documents |
| GET | `/conversation/history` | — | Chat history |
| POST | `/conversation/session` | — | Create/switch session |
| GET | `/conversation/sessions` | — | List sessions |
| DELETE | `/conversation/session/{id}` | — | Delete session |

### Feedback & Suggestions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/feedback` | — | Submit feedback |
| GET | `/feedback/stats` | — | Feedback statistics |
| GET | `/suggestions` | — | Query suggestions |
| GET | `/suggestions/related` | — | Related queries |

### Cost & Analytics

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/cost/summary` | — | Cost summary |
| GET | `/cost/budget` | — | Budget check |
| GET | `/cost/savings` | — | Cost savings from routing |
| GET | `/cost/breakdown` | — | Cost by category/company |
| GET | `/cost/token-budgets` | — | Token usage by model |
| GET | `/analytics/models` | — | Model comparison |
| GET | `/analytics/routing` | — | Routing breakdown |
| GET | `/analytics/trend` | — | Cost trend |
| GET | `/analytics/tokens` | — | Token efficiency |
| GET | `/analytics/anomalies` | — | Anomaly detection |

### Latency & Cache

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/latency/stats` | — | p50/p95/p99 per component |
| GET | `/latency/recent` | — | Recent latency entries |
| GET | `/latency/trend` | — | Time-bucketed averages |
| GET | `/cache/stats` | — | Semantic cache hit rates |

### Prompts

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/prompts` | — | List all prompts + versions |
| GET | `/prompts/{name}` | — | Get prompt details |
| POST | `/prompts/{name}/rollback` | — | Rollback to version |
| POST | `/prompts/{name}/regression` | — | Run regression test |

### Compare Filings

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/compare/years` | — | Compare company across years |
| POST | `/compare/companies` | — | Compare companies for a year |

### Tenants (auth required)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/tenants` | require_admin | Create tenant |
| GET | `/tenants` | require_admin | List tenants |
| GET | `/tenants/{id}` | require_admin | Get tenant |
| PUT | `/tenants/{id}` | require_admin | Update tenant |
| DELETE | `/tenants/{id}` | require_admin | Delete tenant |
| GET | `/tenants/{id}/usage` | require_admin | Usage stats |

### Admin (auth required)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/admin/login` | — | Login (returns token) |
| POST | `/admin/logout` | — | Logout |
| GET | `/admin/validate` | — | Validate session |
| GET | `/admin/users` | require_admin | List users |
| POST | `/admin/users` | require_admin | Create user |
| DELETE | `/admin/users/{id}` | require_admin | Delete user |
| POST | `/admin/clear-cache` | require_admin | Clear cache |

### Knowledge Graph & Eval

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/knowledge/stats` | — | Graph statistics |
| GET | `/knowledge/entity/{id}` | — | Query entity |
| POST | `/knowledge/extract` | — | Extract from text |
| POST | `/eval/run` | — | Run evaluation |
| GET | `/eval/history` | — | Eval history |
| GET | `/eval/averages` | — | Average scores |

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | — | System health |
| GET | `/health/metrics` | — | Health metrics |

---

## 4. Frontend

### Jinja2 Templates (9 pages, server-rendered)

| Page | Template | Key Endpoints |
|------|----------|---------------|
| Landing | `index.html` | `GET /health` |
| Chat | `app.html` | `POST /query/stream` (SSE), `GET /suggestions`, `POST /feedback` |
| Upload | `upload.html` | `POST /upload`, `GET /upload/{doc_id}/status` |
| Documents | `documents.html` | `GET /documents` |
| Analytics | `analytics.html` | `GET /analytics/*`, `GET /cost/*` |
| Comparison | `comparison.html` | `GET /analytics/models` |
| Latency | `latency.html` | `GET /latency/stats`, `GET /latency/trend` |
| Cost Optimization | `cost_optimization.html` | `GET /cost/savings`, `GET /cost/token-budgets` |
| Admin | `admin.html` | `POST /admin/login`, CRUD users/tenants |

**Archived**: `frontend-archived/` (Next.js), `dashboard-archived/` (Streamlit) — local only, not in git.

---

## 5. Data Flow

### Query Flow (Primary)

```
User sends query
    │
    ▼
┌─────────────────────────────┐
│  api/routes/query.py        │
│  POST /query                │
│  1. Validate tenant         │
│  2. Check budget            │
│  3. Input guardrails        │
└─────────┬───────────────────┘
          │
    ┌─────▼──────────────────┐
    │ LangGraphOrchestrator  │
    │ (graph.py)             │
    └─────┬──────────────────┘
          │
    ┌─────▼──────────────────┐
    │ 1. planner_node        │ ← CostAwareRouter → model selection
    │ 2. tool_executor_node  │ ← HybridRetriever (vector+BM25+RRF+reranker)
    │ 3. generator_node      │ ← OllamaClient.chat() + cost accumulation
    │ 4. reflector_node      │ ← Self-reflection (bounded loop)
    └─────┬──────────────────┘
          │
    ┌─────▼──────────────────┐
    │ Tenant filtering       │ ← Filter by allowed tickers
    │ Output guardrails      │ ← Grounding check, cross-ref validation
    │ CostTracker            │ ← Log cost, latency, tokens
    │ AuditLogger            │ ← Log query event
    └─────┬──────────────────┘
          │
    ▼
  Response → Frontend
```

### Ingestion Flow

```
POST /upload  or  scripts/ingest.py
    │
    ▼
┌─────────────────────┐
│ download/validate   │ ← SEC EDGAR API or file upload
└─────┬───────────────┘
      │
┌─────▼───────────────┐
│ parser.py           │ ← Docling parse → chunks with metadata
└─────┬───────────────┘
      │
┌─────▼───────────────┐
│ chunker.py          │ ← SemanticChunker (parent-child, overlap)
└─────┬───────────────┘
      │
┌─────▼───────────────┐
│ VectorStore + BM25  │ ← ChromaDB + BM25 index
└─────────────────────┘
```

### Eval Flow

```
python -m src.eval.harness
    │
    ▼
┌─────────────────────┐
│ Load golden set     │ ← data/eval/golden_set.json (20 entries)
└─────┬───────────────┘
      │
┌─────▼───────────────┐
│ Run each query      │ ← LangGraphOrchestrator.run()
│ Track cost + latency│
└─────┬───────────────┘
      │
┌─────▼───────────────┐
│ LLM Judge           │ ← minimax-m3:cloud (structured JSON)
│ Retrieval metrics   │ ← NDCG, MRR, Recall, Precision
└─────┬───────────────┘
      │
┌─────▼───────────────┐
│ Failure buckets     │ ← correct/partial/wrong_answer/no_answer/timeout
│ CI gating           │ ← overall>=0.7, faithfulness>=0.5
│ Baseline comparison │ ← --baseline flag
└─────────────────────┘
```

---

## 6. External Services

| Service | Config | Used By |
|---------|--------|---------|
| **Ollama Cloud** | `OLLAMA_BASE_URL`, `OLLAMA_API_KEY` | LLMClient — gemma3:4b, gemma3:27b, minimax-m3:cloud |
| **SEC EDGAR** | Hardcoded URLs | downloader.py — fetch 10-K filings |
| **Redis** | `REDIS_URL` (optional) | CacheManager — query cache |
| **Langfuse** | `LANGFUSE_*` (optional) | Observability — flat traces |
| **OpenTelemetry** | `OTEL_EXPORTER_OTLP_ENDPOINT` (optional) | Tracing — distributed spans |

---

## 7. Model Stack

| Model | Size | Location | Function |
|-------|------|----------|----------|
| `BAAI/bge-small-en-v1.5` | 384d | Local | Embeddings (ChromaDB) |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | 22M | Local | Reranking retrieval results |
| `gemma3:4b` | 4B | Ollama Cloud | Simple queries (cost: $0.075/1M tokens) |
| `gemma3:27b` | 27B | Ollama Cloud | Complex queries + vision (cost: $0.30/1M tokens) |
| `minimax-m3:cloud` | Large | Ollama Cloud | LLM-as-Judge evaluation |
| `TF-IDF + LogisticRegression` | — | Local (sklearn) | Query complexity classification (110 training examples) |

---

## 8. Security Model

| Layer | Implementation |
|-------|---------------|
| **Admin auth** | bcrypt passwords, `require_admin` dependency on admin/tenant routes |
| **Tenant isolation** | `tenant_id` in orchestrator, context filtered by allowed tickers |
| **Input guardrails** | PII detection, prompt injection, length limits |
| **Output guardrails** | Cross-reference amount check, semantic grounding |
| **RBAC** | Document-level access control (src/retrieval/rbac.py) |
| **Semantic cache** | Cosine similarity 0.92 threshold |
| **CORS** | Whitelist localhost:8001 and localhost:3000 |
| **Audit logging** | JSONL trail for admin actions, auth attempts, queries |

---

## 9. Key Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **LangGraph over while-loop** | Proper state machine, not ad-hoc loop |
| **bge-small-en-v1.5 over nomic-embed-text** | nomic caused segfault on Windows |
| **RRF over weighted-sum fusion** | More robust to scale differences between retrievers |
| **Trained classifier over keyword matching** | 110 labeled examples, F1 metrics, confusion matrix |
| **Cross-encoder for reranking** | +15-30% retrieval improvement over vanilla BM25+vector |
| **Parent-child chunking** | Small for retrieval precision, large for LLM context |
| **NetworkX for knowledge graph** | Lightweight, no external DB |
| **bcrypt over SHA-256** | Production-grade password hashing |
| **No auto-create admin** | Security — credentials via env vars only |
| **ONE frontend (Jinja2)** | Stop indecision, archived Next.js + Streamlit |
| **Python-based Docker healthcheck** | No curl dependency in slim image |
| **Eval harness with failure buckets** | Actionable diagnostics, not just scores |
| **OpenTelemetry + Langfuse** | Dual observability (OTel for vendor-neutral, Langfuse for UI) |

---

## 10. Dead Code

| File | Reason |
|------|--------|
| `src/database/models.py` | SQLAlchemy models, not used (file-based storage) |
| `src/tasks/celery_app.py` | Celery tasks, never triggered |
