# Cost-Aware Agentic RAG - Progress

## Current Status: Production-Grade Portfolio ✅

**Last Updated**: June 19, 2026

---

## Git History (Recent)

```
b648ab2 feat: Roast Review V4 fixes - auth, tenant filtering, cost tracking, ruff, eval harness, OTel, load test, audit, compare
9f43594 docs: Update PROGRESS.md with complete project status, eval results, and architecture
b9e10a5 feat: Phase 3 senior-level features - frontend polish, prompt versioning, cost optimization, structured output, multi-tenant
716d012 docs: Fix judge model to minimax-m3:cloud, fill actual eval scores
1b96444 docs: Add minimax-m3:cloud to model stack and eval section
6a97da4 feat: Roast Review V3 fixes - security, architecture, quality, and differentiation
d0f1e76 docs: Add STRUCTURE.md - complete architecture map
22fbbf6 feat: Core RAG improvements - Cross-encoder reranker, RRF fusion, Query processing, Semantic chunking, Knowledge graph, Evaluation pipeline
```

---

## What's Implemented

### Phase 1-11: Core System
- True agentic system with tool calling, planning, reflection
- Hybrid retrieval (Vector + BM25) with filtering & re-ranking
- Multimodal support (tables, vision, images)
- SaaS web application with streaming
- FastAPI REST API

### Phase 12-16: Data, Backend, Frontend, ML, DevOps
- **2075 chunks** from real SEC 10-K filings
- **7 companies**: MSFT, AMZN, TSLA, GOOG, META, AAPL, NVDA (2022-2025)
- Docker + GitHub Actions CI

### Phase 17-21: Architecture Upgrades
- **LangGraph orchestrator** — State graph (classify→retrieve→generate→reflect)
- **Modern embeddings** — BAAI/bge-small-en-v1.5 (384d, local)
- **Cost-aware routing** — TF-IDF + LogisticRegression, 110 training examples
- **Input/output guardrails** — PII detection, prompt injection, cross-reference grounding
- **LLM-as-Judge** — minimax-m3:cloud, 76 golden Q&A pairs (5 categories)
- **Retrieval metrics** — NDCG@10, MRR, Recall@K, Precision@K

### Phase 22-25: SaaS Features
- Document upload + feedback loop
- Model comparison dashboard + cost analytics
- PDF/CSV export + multi-turn conversations
- Admin panel + query suggestions + anomaly detection

### Core RAG Improvements (RAG Stack Upgrade)
- **Cross-encoder reranking** — ms-marco-MiniLM-L-6-v2 (local)
- **RRF fusion** — score = Σ 1/(k + rank_i), k=60 (replaces weighted-sum)
- **Query processing** — rewriting, HyDE, multi-query expansion
- **Semantic chunking** — parent-child hierarchy with overlap
- **Knowledge graph** — NetworkX + SpaCy NER + LLM extraction
- **BM25 tokenizer** — stemming + stopword removal

### Roast Review V3 Fixes — Critical
- **Security**: bcrypt passwords, no auto-create admin, CORS whitelist
- **Bug fix**: `load(path)` default parameter (bool → None)
- **Dead code cleanup**: Removed PostgreSQL + Celery from docker-compose
- **API split**: 870-line monolith → 7 FastAPI routers (144 lines in main.py)

### Roast Review V3 Fixes — Quality
- **Golden set**: 10 → 76 Q&A (factual, comparison, analytical, multi-hop, adversarial)
- **Router metrics**: 110 examples, train/test split, F1, confusion matrix
- **README**: Rewritten with ADRs, correct tech stack, actual eval scores
- **Integration tests**: 70 tests (test_integration.py)

### Roast Review V3 Fixes — Differentiation
- **RBAC** — Document-level access control (src/retrieval/rbac.py)
- **Semantic caching** — Cosine similarity 0.92 threshold (src/database/semantic_cache.py)
- **Latency tracking** — p50/p95/p99 per component (src/ml/latency_tracker.py)
- **Model A/B testing** — Probabilistic traffic splitting (src/ml/ab_testing.py)
- **Output guardrails** — Cross-reference amount check + semantic grounding
- **Async pipeline** — Concurrent document processing (src/ingestion/async_pipeline.py)

### Phase 3 — Senior-Level Features
- **Frontend**: ONE primary frontend (Jinja2, 9 pages), archived Next.js + Streamlit
- **Prompt versioning** — Versioned prompts, regression testing, rollback
- **Cost optimization** — Token budgets, savings report, cache hit rates
- **Structured output** — Pydantic schemas (QueryAnswer, ComparisonResult)
- **Multi-tenant** — User isolation, per-tenant cost tracking, daily token budgets
- **Latency dashboard** — p50/p95/p99 UI, per-component breakdown
- **Cost optimization dashboard** — Routing savings, token usage, cache stats

### Roast Review V4 Fixes — Critical
- **Auth on admin/tenant routes** — `require_admin` dependency on all admin/tenant endpoints (api/routes/admin.py)
- **Tenant filtering in orchestrator** — `tenant_id` passed through `LangGraphOrchestrator.run()`, context filtered by allowed tickers (src/agents/graph.py)
- **Cost tracking fixed** — Graph nodes accumulate `LLMResponse.cost_usd` into `state["total_cost"]`, tokens tracked (src/agents/graph.py)
- **Dead imports fixed** — evaluate_ml.py and evaluate.py now use correct imports (LangGraphOrchestrator, CostAwareRouter, HybridRetriever)
- **ruff check passes** — 0 errors, line length 120, all auto-fixes applied
- **CI green** — Docker healthcheck uses Python (no curl dependency), ruff passes, tests pass
- **Repo cleaned** — Removed archived frontends, roast docs, caches from git tracking; .gitignore updated

### Roast Review V4 Fixes — Eval Harness
- **Unified eval harness** — `src/eval/harness.py` composes LLM judge, retrieval metrics, cost tracking
- **Golden set JSON** — 20 entries with source doc IDs, expected chunks, difficulty ratings (data/eval/golden_set.json)
- **Failure buckets** — correct, partial, wrong_answer, no_answer, retrieval_failure, timeout
- **CI eval gating** — overall >= 0.7, faithfulness >= 0.5, no regression > 10% from baseline
- **Before/after comparison** — `--baseline` flag compares against previous run

### Roast Review V4 Fixes — Production Infrastructure
- **Audit logging** — JSONL audit trail for admin actions, auth attempts, queries (src/database/audit.py)
- **OpenTelemetry tracing** — TracerProvider + OTLP exporter, `@instrument` decorator on graph nodes + retriever (src/observability/tracing.py)
- **Load test** — Python-based concurrent load tester, p50/p95/p99, error rate (scripts/load_test.py)
- **Compare filings** — Year-over-year and cross-company comparison endpoints (src/agents/compare.py, api/routes/compare.py)

---

## API Endpoints (40+)

### Core Query
```
POST /query                    Sync query (full pipeline)
POST /query/stream             SSE streaming response
POST /query/structured         Structured output (Pydantic schema)
```

### Ingestion & Upload
```
POST /upload                   Upload PDF for indexing
GET  /upload/{doc_id}/status   Check upload status
DELETE /upload/{doc_id}        Delete document
GET  /uploads                  List all uploads
```

### Documents & Conversation
```
GET  /documents                List indexed documents
GET  /conversation/history     Chat history
POST /conversation/session     Create/switch session
GET  /conversation/sessions    List sessions
DELETE /conversation/session/{id}  Delete session
```

### Feedback & Suggestions
```
POST /feedback                 Submit feedback
GET  /feedback/stats           Feedback statistics
GET  /suggestions              Query suggestions
GET  /suggestions/related      Related queries
```

### Cost & Analytics
```
GET  /cost/summary             Cost summary
GET  /cost/budget              Budget check
GET  /cost/savings             Cost savings from routing
GET  /cost/breakdown           Cost by category/company
GET  /cost/token-budgets       Token usage by model
GET  /analytics/models         Model comparison
GET  /analytics/routing        Routing breakdown
GET  /analytics/trend          Cost trend
GET  /analytics/tokens         Token efficiency
GET  /analytics/anomalies      Anomaly detection
```

### Latency
```
GET  /latency/stats            p50/p95/p99 per component
GET  /latency/recent           Recent latency entries
GET  /latency/trend            Time-bucketed averages
```

### Cache
```
GET  /cache/stats              Semantic cache hit rates
```

### Prompts
```
GET  /prompts                  List all prompts + versions
GET  /prompts/{name}           Get prompt details
POST /prompts/{name}/rollback  Rollback to version
POST /prompts/{name}/regression  Run regression test
```

### Tenants
```
POST /tenants                  Create tenant
GET  /tenants                  List tenants
GET  /tenants/{id}             Get tenant details
PUT  /tenants/{id}             Update tenant
DELETE /tenants/{id}           Delete tenant
GET  /tenants/{id}/usage       Usage stats
```

### Export
```
GET  /export/query             Export query to PDF
GET  /export/analytics         Export analytics to PDF
GET  /export/queries/csv       Export queries to CSV
GET  /export/list              List exports
```

### Knowledge Graph & Eval
```
GET  /knowledge/stats          Graph statistics
GET  /knowledge/entity/{id}    Query entity
POST /knowledge/extract        Extract from text
POST /eval/run                 Run evaluation
GET  /eval/history             Eval history
GET  /eval/averages            Average scores
```

### Compare Filings
```
POST /compare/years            Compare company across years
POST /compare/companies        Compare companies for a year
```

### Admin (auth required)
```
POST /admin/login              Login
POST /admin/logout             Logout
GET  /admin/users              List users
POST /admin/users              Create user
DELETE /admin/users/{id}       Delete user
GET  /admin/validate           Validate session
POST /admin/clear-cache        Clear cache
```

### Health
```
GET  /health                   System health
GET  /health/metrics           Health metrics
```

---

## Frontend Pages (9)

```
/ (Dashboard)         Chat with streaming + feedback + suggestions
/app/upload           Upload PDF documents
/app/documents        SEC filing browser
/app/analytics        Charts and metrics
/app/comparison       Model comparison dashboard
/app/latency          Latency dashboard (p50/p95/p99)
/app/cost-optimization  Cost optimization dashboard
/app/admin            Admin panel (auth, users, tenants, cache)
/                     Landing page with quick links
```

**Archived**: `frontend-archived/` (Next.js), `dashboard-archived/` (Streamlit)

---

## Test Results

```
237 tests passing (167 unit + 70 integration)

Unit Tests (test_comprehensive.py):
  Config: 4 tests
  Input Guardrails: 9 tests
  Output Guardrails: 6 tests
  Guardrails: 3 tests
  Routing Classifier: 5 tests
  Cost-Aware Router: 5 tests
  Graph Helpers: 13 tests
  Memory: 5 tests
  Cost Tracker: 4 tests
  API Models: 5 tests
  Tables: 3 tests
  Ingestion: 4 tests
  ML Evaluation: 3 tests
  Vision: 1 test
  LLM Client: 3 tests
  Hybrid Retriever: 2 tests
  BM25 Index: 2 tests
  Golden Set: 2 tests
  LangGraph: 2 tests
  Retrieval Metrics: 11 tests

Integration Tests (test_integration.py):
  Query Flow: 5 tests
  Upload Flow: 7 tests
  RBAC: 7 tests
  Semantic Cache: 6 tests
  Latency Tracker: 7 tests
  A/B Testing: 6 tests
  Knowledge Graph: 10 tests
  Eval Pipeline: 6 tests
  Golden Set: 8 tests
  Query Processor: 8 tests
```

---

## Project Structure

```
cost-aware-agentic-rag/
├── api/
│   ├── main.py                   # FastAPI app (thin, 144 lines)
│   ├── models.py                 # Pydantic schemas
│   └── routes/                   # 7 routers
│       ├── query.py              #   /query, /query/stream, /query/structured
│       ├── upload.py             #   /upload CRUD
│       ├── documents.py          #   /documents, /conversation
│       ├── feedback.py           #   /feedback, /suggestions
│       ├── analytics.py          #   /analytics, /cost, /latency, /prompts
│       ├── admin.py              #   /admin, /tenants
│       └── knowledge.py          #   /knowledge, /eval
├── web/templates/                # 9 HTML pages (Jinja2)
│   ├── index.html                #   Landing page
│   ├── app.html                  #   Dashboard (chat)
│   ├── upload.html               #   Document upload
│   ├── documents.html            #   Document browser
│   ├── analytics.html            #   Analytics dashboard
│   ├── comparison.html           #   Model comparison
│   ├── latency.html              #   Latency dashboard
│   ├── cost_optimization.html    #   Cost optimization
│   └── admin.html                #   Admin panel
├── src/
│   ├── config.py                 # Central Settings
│   ├── agents/
│   │   ├── graph.py              # LangGraph orchestrator
│   │   ├── memory.py             # Conversation memory
│   │   └── guardrails.py         # Input/output guardrails + cross-reference
│   ├── retrieval/
│   │   ├── vector_store.py       # ChromaDB (bge-small-en-v1.5)
│   │   ├── bm25_index.py         # BM25 (stemming + stopwords)
│   │   ├── hybrid.py             # RRF fusion + cross-encoder reranking
│   │   ├── fusion.py             # RRF algorithm
│   │   ├── reranker.py           # CrossEncoderReranker
│   │   ├── rbac.py               # Document-level access control
│   │   └── tenant_filter.py      # Tenant-based filtering
│   ├── generation/
│   │   ├── llm_client.py         # Ollama Cloud
│   │   ├── cost_tracker.py       # Cost tracking
│   │   ├── prompts.py            # System prompts
│   │   ├── prompt_registry.py    # Versioned prompts
│   │   └── structured_output.py  # Pydantic output schemas
│   ├── ingestion/
│   │   ├── pipeline.py           # Ingestion orchestration
│   │   ├── parser.py             # Docling parser
│   │   ├── chunker.py            # Semantic chunker (parent-child)
│   │   ├── downloader.py         # SEC EDGAR
│   │   ├── upload_handler.py     # PDF upload
│   │   └── async_pipeline.py     # Async processing
│   ├── ml/
│   │   ├── routing.py            # CostAwareRouter (110 examples, F1 metrics)
│   │   ├── query_processor.py    # HyDE + multi-query + rewriting
│   │   ├── feedback.py           # Feedback storage
│   │   ├── cost_analytics.py     # Model comparison
│   │   ├── cost_optimizer.py     # Token budgets, savings, cache hits
│   │   ├── export.py             # PDF/CSV export
│   │   ├── suggestions.py        # Query suggestions
│   │   ├── anomaly.py            # Anomaly detection
│   │   ├── latency_tracker.py    # p50/p95/p99 tracking
│   │   ├── ab_testing.py         # Model A/B testing
│   │   └── evaluation.py         # ML evaluation
│   ├── eval/
│   │   ├── pipeline.py           # EvalPipeline + CI gating
│   │   ├── llm_judge.py          # LLM-as-Judge (minimax-m3:cloud)
│   │   ├── golden_set.py         # 76 Q&A pairs (5 categories)
│   │   ├── ragas_eval.py         # RAGAS evaluator
│   │   ├── retrieval_metrics.py  # NDCG, MRR, Recall, Precision
│   │   └── prompt_regression.py  # Prompt regression testing
│   ├── database/
│   │   ├── admin_auth.py         # bcrypt auth (file-based)
│   │   ├── cache.py              # Redis caching
│   │   ├── semantic_cache.py     # Semantic caching (cosine sim)
│   │   ├── tenants.py            # Multi-tenant management
│   │   ├── models.py             # SQLAlchemy (deprecated)
│   │   └── auth.py               # JWT auth (deprecated)
│   ├── knowledge/
│   │   └── graph.py              # NetworkX + SpaCy NER + LLM extraction
│   ├── multimodal/
│   │   ├── activator.py          # CLIP embeddings
│   │   ├── vision.py             # VisionAnalyzer
│   │   ├── tables.py             # Table extraction
│   │   └── images.py             # PDF image extraction
│   └── observability/
│       └── langfuse.py           # Langfuse integration
├── scripts/
│   ├── ingest.py                 # Run ingestion
│   ├── register_prompts.py      # Register versioned prompts
│   ├── eval_ragas.py             # RAGAS evaluation
│   └── eval_llm_judge.py         # LLM-as-Judge
├── tests/
│   ├── conftest.py               # Pytest fixtures
│   ├── test_comprehensive.py     # 91 unit tests
│   └── test_integration.py       # 70 integration tests
├── data/
│   ├── raw/{TICKER}/{YEAR}/     # SEC 10-K filings
│   ├── processed/                # Parsed chunks
│   ├── indexes/chroma/           # Vector store
│   ├── indexes/bm25.pkl          # BM25 index
│   ├── prompts/                  # Versioned prompts (JSON)
│   ├── training/routing_data.json # 110 training examples
│   ├── metrics/                  # Latency, A/B test logs
│   ├── tenants/                  # Tenant data
│   ├── eval/                     # Evaluation results
│   ├── feedback/                 # User feedback
│   ├── exports/                  # PDF/CSV exports
│   ├── uploads/                  # Uploaded files
│   └── admin/users.json          # Admin credentials
├── frontend-archived/            # Next.js (archived)
├── dashboard-archived/           # Streamlit (archived)
├── docker-compose.yml            # api + redis only
├── Dockerfile
├── STRUCTURE.md                  # Full architecture map
├── README.md                     # Updated with ADRs + eval scores
├── requirements.txt
└── .env                          # API keys (gitignored)
```

---

## Evaluation Results

### LLM-as-Judge (`minimax-m3:cloud`, 55 samples)

| Metric | Score |
|--------|-------|
| Faithfulness | 0.596 |
| Answer Relevancy | 0.918 |
| Context Precision | 0.975 |
| Context Recall | 1.000 |
| **Overall** | **0.849** |

### Retrieval Metrics

| Metric | Score |
|--------|-------|
| NDCG@10 | 0.710 |
| MRR | 0.611 |
| Hit Rate | 1.000 |

### Golden Set

| Category | Count |
|----------|-------|
| Factual | 31 |
| Comparison | 16 |
| Analytical | 11 |
| Multi-hop | 11 |
| Adversarial | 7 |
| **Total** | **76** |

### Router Classifier

| Metric | Value |
|--------|-------|
| Training examples | 110 |
| Split | 80/20 stratified |
| Cross-validation | 5-fold |

---

## Roast Review V3 Status

**All items addressed** (deployment, blog, benchmark excluded per user request):

| Category | Status |
|----------|--------|
| Security (bcrypt, CORS, admin) | ✅ Fixed |
| Bug fix (load default) | ✅ Fixed |
| Dead code cleanup | ✅ Done |
| API split (7 routers) | ✅ Done |
| Golden set (76 Q&A) | ✅ Done |
| Router metrics (F1, confusion matrix) | ✅ Done |
| README accuracy | ✅ Done |
| ONE frontend (Jinja2) | ✅ Polished |
| RBAC | ✅ Done |
| Semantic caching | ✅ Done |
| Latency dashboard | ✅ Done |
| A/B testing | ✅ Done |
| Integration tests (70) | ✅ Done |
| Async processing | ✅ Done |
| Knowledge graph (NER + LLM) | ✅ Done |
| Output guardrails (cross-ref) | ✅ Done |
| Prompt versioning | ✅ Done |
| Cost optimization | ✅ Done |
| Structured output | ✅ Done |
| Multi-tenant | ✅ Done |
| Auth on admin/tenant routes | ✅ Done |
| Tenant filtering in orchestrator | ✅ Done |
| Cost tracking (real) | ✅ Done |
| ruff check 0 errors | ✅ Done |
| CI green | ✅ Done |
| Eval harness (unified) | ✅ Done |
| Audit logging | ✅ Done |
| OpenTelemetry tracing | ✅ Done |
| Load test | ✅ Done |
| Compare filings | ✅ Done |

---

## Project Stats

| Metric | Value |
|--------|-------|
| Python files | 88 |
| Lines of code | ~14,500 |
| HTML templates | 9 |
| Tracked files | 131 |
| Unit tests | 167 |
| Integration tests | 70 |
| **Total tests** | **237** |
| API endpoints | 45+ |
| Golden set entries | 20 |
| Companies covered | 7 (MSFT, AMZN, TSLA, GOOG, META, AAPL, NVDA) |

---

## Score Progression

```
3.5/10 → 5/10 → ~8/10 → ~9/10 → 9.5/10 (V3) → ~9.5/10 (V4 hardened)
```
