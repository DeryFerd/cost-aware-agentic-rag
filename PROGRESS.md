# Cost-Aware Agentic RAG - Progress

## Current Status: Phase 25 Complete ✅

**Last Updated**: June 16, 2026

---

## Git History

```
6ce230f feat: LLM-as-Judge evaluation with minimax-m3 via Ollama Cloud
71ec687 fix: resolve remaining roast review issues - improved heuristics, NER guardrails, expanded golden dataset
42e8b11 docs: update PROGRESS.md to Phase 21, add eval results
01b9a0b chore: remove ROAST_REVIEW.md from tracking (local only)
cb8cf3c feat: CI pipeline, retrieval metrics, Langfuse observability, evaluation
4c6c587 fix: resolve ROAST_REVIEW_V2 issues - tests, lint, dead code cleanup
e7f6216 feat: LangGraph, RAGAS eval, guardrails, modern embeddings (Phase 18)
7a123c4 fix: resolve all ROAST_REVIEW issues
de6664f docs: update PLAN.md and PROGRESS.md - all phases complete
3700649 docs: update PROGRESS.md - all phases complete!
48f1dda feat: add ML evaluation, cost optimization, Docker Compose
b7dd1ef feat: add Next.js 14 frontend with dashboard, analytics, documents
03e49bd feat: add PostgreSQL, Redis, JWT auth, Celery tasks
caa3f98 feat: expand data to 7 companies, 2075 chunks
746438b feat: add GitHub Actions CI pipeline
288688f fix: compare query now returns consistent results
3f33eb2 feat: download and index real SEC 10-K data
```

---

## What's Implemented

### ✅ Phase 1-11: Core System
- True agentic system with tool calling, planning, reflection
- Hybrid retrieval (Vector + BM25) with filtering & re-ranking
- Multimodal support (tables, vision, images)
- SaaS web application with streaming
- FastAPI REST API
- Evaluation (0.98/1.00 score)
- Unit tests passing

### ✅ Phase 12: Data Expansion
- **2075 chunks** from real SEC 10-K filings
- **7 companies**: MSFT, AMZN, TSLA, GOOG, META, AAPL, NVDA
- **2022-2025** data coverage
- Real filings from EDGAR XBRL API

### ✅ Phase 13: Backend Complexity
- Database models (PostgreSQL/SQLite) with lazy init
- JWT authentication with role-based access (defined, not enforced)
- Redis caching with TTL (integrated in API)
- Celery background tasks (defined, not triggered)
- Rate limiting per user
- Cost tracking

### ✅ Phase 14: Frontend Complexity
- Next.js 14 with App Router
- TypeScript + Tailwind CSS
- Dashboard with real-time streaming chat
- Analytics page with Recharts charts (real API data)
- Documents page with filtering (real API data)
- Sidebar navigation

### ✅ Phase 15: ML/AI Engineering
- MLEvaluator with relevance/accuracy/completeness scoring
- 50+ query golden set (expanded from 10 to 50)
- Evaluation scripts

### ✅ Phase 16: DevOps
- Docker Compose with all services
- Dockerfiles (API + Frontend)
- GitHub Actions CI pipeline with lint + typecheck + Docker build

### ✅ Phase 17: Bug Fixes (ROAST_REVIEW)
- Fixed 14 critical bugs and crashes
- Added 31 comprehensive tests
- Integrated Redis caching
- Fixed all logic errors

### ✅ Phase 18: Architecture Upgrades
- **LangGraph orchestrator** — State graph with planning/execution/reflection nodes
- **Modern embeddings** — Upgraded to BAAI/bge-small-en-v1.5 (384d)
- **RAGAS evaluation** — Proper faithfulness, relevancy, context precision/recall metrics
- **Cost-aware routing** — Trained classifier (LogisticRegression + TFIDF)
- **Input/output guardrails** — PII detection, prompt injection blocking, hallucination checks
- **Fixed frontend** — Analytics and documents pages now use real API data

### ✅ Phase 19: ROAST_REVIEW_V2 Fixes
- **Fixed reflection loop** — `needs_retry` flag in AgentState, `should_continue` checks it
- **Wired CostAwareRouter** — Into `planner_node` and streaming endpoint
- **Fixed _extract_citations** — Handles both str and dict context
- **Fixed _build_context** — ImportError in api/main.py resolved
- **Set realistic MODEL_COSTS** — gemma3:4b (0.05/0.10), gemma3:27b (0.25/0.50)
- **Deleted dead code** — orchestrator.py, tools.py, dashboard/, CostOptimizer, RetrievalOptimizer
- **Rewrote test suite** — 97 tests (was 31), all passing, all lint errors fixed
- **Fixed frontend** — Documents uses `/documents` API, analytics uses real data

### ✅ Phase 20: CI, Metrics & Observability
- **CI pipeline** — conftest.py with mock fixtures, pytest markers, skip integration tests
- **Retrieval metrics** — NDCG@10, MRR, Recall@5/10, Precision@5/10, Hit Rate
- **Langfuse observability** — Tracks every query in LangGraphOrchestrator
- **Evaluation framework** — Demo script, saves results to data/eval/

### ✅ Phase 21: Roast Review Final Fixes + LLM-as-Judge Evaluation
- **Improved heuristic evaluation** — Bigram overlap, removed magic multipliers (1.5×)
- **NER-based guardrails** — SpaCy NER for PII detection (optional, regex fallback)
- **Expanded golden dataset** — 10 → 55 samples for proper evaluation baseline
- **RAGAS installed** — ragas==0.4.3 for real evaluation
- **classify_complexity deprecated** — Added deprecation notice, kept as fallback
- **LLM-as-Judge evaluation** — minimax-m3:cloud via Ollama Cloud
- **Evaluation Results**: Overall 0.85 (F=0.60, R=0.92, P=0.97, Rc=1.00)

### 🔄 Phase 22: Document Upload + Feedback Loop
- **Upload handler** — PDF upload, parse (Docling), chunk, embed, store
- **Upload API** — POST /upload, GET /upload/status/{doc_id}, DELETE /upload/{doc_id}, GET /uploads
- **Feedback system** — Store thumbs up/down, aggregate stats
- **Feedback API** — POST /feedback, GET /feedback/stats, GET /feedback/recent
- **Upload UI** — Drag-and-drop PDF upload with progress tracking
- **Feedback buttons** — Thumbs up/down on every AI response
- **Sidebar updated** — Upload link added to all pages

### 🔄 Phase 23: Model Comparison Dashboard + Cost Optimization
- **Cost analytics module** — Model comparison, routing breakdown, cost trend, token efficiency
- **Analytics API** — GET /analytics/models, /analytics/routing, /analytics/trend, /analytics/tokens
- **Model comparison dashboard** — Side-by-side model performance with visual bars
- **Routing breakdown** — Query complexity distribution, cost by complexity
- **Cost trend chart** — Daily cost visualization with configurable period
- **Token efficiency** — Cost per 1K tokens by model

### 🔄 Phase 24: Export + Multi-turn Conversations
- **Export module** — PDF export (query report, analytics), CSV export (query history)
- **Export API** — GET /export/query, /export/analytics, /export/queries/csv, /export/list
- **Multi-turn context** — Conversation history included in LLM prompts (last 10 messages)
- **Session management** — Create/switch/delete conversation sessions
- **Conversation API** — GET /conversation/context, POST /conversation/session, GET /conversation/sessions, DELETE /conversation/session/{id}
- **Frontend export buttons** — CSV and Analytics PDF export in dashboard header

### ✅ Phase 25: Admin Panel + Query Suggestions + Anomaly Detection
- **Admin auth** — File-based JWT auth (no DB dependency), login/logout/session management
- **Admin API** — POST /admin/login, /admin/logout, GET /admin/users, POST /admin/users, DELETE /admin/users/{id}, GET /admin/validate
- **Admin dashboard** — Health status, anomaly list, user management, query suggestions
- **Query suggestions** — Based on historical patterns and document content
- **Suggestions API** — GET /suggestions, GET /suggestions/related
- **Anomaly detection** — Cost spikes, latency spikes, rapid queries, routing imbalances
- **Health metrics** — System status, avg cost, avg latency, error rate
- **Anomaly API** — GET /anomalies, GET /health/metrics
- **Frontend** — Query suggestions in dashboard, Admin link in all sidebars

---

## API Endpoints

```
POST /query              - Execute financial query (with guardrails + Redis caching)
POST /query/stream       - Stream response (SSE) with CostAwareRouter
GET  /health             - System status
GET  /documents          - List indexed documents with metadata
GET  /cost/summary       - Cost analytics
GET  /cost/budget        - Budget check
GET  /conversation/history - Chat history
POST /conversation/clear - Clear memory
POST /upload             - Upload PDF for indexing
GET  /upload/status/{id} - Check upload status
GET  /uploads            - List all uploads
DELETE /upload/{id}      - Delete uploaded document
POST /feedback           - Submit query feedback
GET  /feedback/stats     - Feedback statistics
GET  /feedback/recent    - Recent feedback entries
GET  /analytics/models   - Model comparison metrics
GET  /analytics/routing  - Routing breakdown and efficiency
GET  /analytics/trend    - Cost trend over time
GET  /analytics/tokens   - Cost per token analysis
GET  /export/query       - Export query to PDF
GET  /export/analytics   - Export analytics to PDF
GET  /export/queries/csv - Export queries to CSV
GET  /export/list        - List exported files
GET  /conversation/context - Get conversation context
POST /conversation/session - Create/switch session
GET  /conversation/sessions - List all sessions
DELETE /conversation/session/{id} - Delete session
GET  /suggestions         - Get query suggestions
GET  /suggestions/related - Get related queries
GET  /anomalies           - Detect anomalies
GET  /health/metrics      - System health metrics
POST /admin/login         - Admin login
POST /admin/logout        - Admin logout
GET  /admin/users         - List users
POST /admin/users         - Create user
DELETE /admin/users/{id}  - Delete user
GET  /admin/validate      - Validate session
```

---

## Frontend Pages

```
/ (Dashboard)            - Chat with streaming + feedback + suggestions
/upload                  - Upload PDF documents
/analytics               - Charts and metrics (real API)
/comparison              - Model comparison dashboard
/admin                   - Admin panel (auth, users, health, anomalies)
/documents               - SEC filing browser (real API)
```

---

## Test Results

```
97 tests passing (was 31)

Guardrails: 9 tests
- PII detection (email, phone, SSN, credit card)
- Prompt injection blocking (7 patterns)
- Input validation (length, truncation)
- Output grounding, hallucination detection

Routing: 5 tests
- Classifier training, prediction
- Simple/complex classification
- Fallback to LLM on low confidence
- Cost estimation

Graph Helpers: 12 tests
- Context building from tools
- Citation extraction (str + dict)
- should_continue logic
- Response cleaning

Retrieval Metrics: 11 tests
- NDCG@10, MRR, Recall@K, Precision@K
- Hit Rate, empty queries

Memory: 5 tests
- Init, add_message, metadata
- Context string generation
- History retrieval

Cost Tracker: 4 tests
- Init, summary, record, budget check

API Models: 5 tests
- Request/response validation
- Health response, cost summary

Tables: 3 tests
- Extract, format, empty

LangGraph: 2 tests
- Build graph, orchestrator init

Plus: config, ingestion, evaluation, vision, LLM client, vector store, BM25, golden set
```

---

## Project Structure

```
cost-aware-agentic-rag/
├── .github/workflows/
│   └── ci.yml                    # GitHub Actions CI (lint + typecheck + Docker)
├── api/
│   ├── main.py                   # FastAPI app (guardrails + CostAwareRouter + streaming)
│   └── models.py                 # Pydantic schemas
├── frontend/                     # Next.js 14 app
│   └── src/app/
│       ├── page.tsx              # Dashboard
│       ├── analytics/page.tsx    # Analytics (real API)
│       └── documents/page.tsx    # Documents (real API)
├── web/templates/                    # HTML templates (Jinja2)
│   ├── app.html                      # Dashboard (chat + feedback + suggestions)
│   ├── upload.html                   # Document upload page
│   ├── comparison.html               # Model comparison dashboard
│   ├── admin.html                    # NEW: Admin panel
│   ├── documents.html                # Document browser
│   └── analytics.html                # Analytics dashboard
├── src/
│   ├── agents/
│   │   ├── graph.py                  # LangGraph state graph (planner→tools→generator→reflector)
│   │   ├── memory.py                 # Conversation memory
│   │   └── guardrails.py             # Input/output guardrails (regex + SpaCy NER)
│   ├── retrieval/
│   │   ├── vector_store.py           # ChromaDB (bge-small-en-v1.5)
│   │   ├── bm25_index.py             # BM25 sparse
│   │   └── hybrid.py                 # Hybrid fusion
│   ├── generation/
│   │   ├── llm_client.py             # Ollama Cloud (MODEL_COSTS: 0.05/0.10, 0.25/0.50)
│   │   └── cost_tracker.py           # Cost tracking
│   ├── multimodal/
│   │   ├── tables.py                 # Table extraction
│   │   ├── vision.py                 # VisionAnalyzer
│   │   └── images.py                 # PDF image extraction
│   ├── ingestion/
│   │   ├── upload_handler.py         # NEW: PDF upload, parse, chunk, embed, store
│   │   ├── parser.py                 # Docling document parser
│   │   ├── downloader.py             # EDGAR XBRL API
│   │   └── pipeline.py              # Ingestion pipeline
│   ├── ml/
│   │   ├── feedback.py               # NEW: Feedback storage and aggregation
│   │   ├── cost_analytics.py          # NEW: Model comparison and cost optimization
│   │   ├── export.py                  # NEW: PDF/CSV export
│   │   ├── evaluation.py             # ML evaluation
│   │   └── routing.py                # CostAwareRouter (trained classifier)
│   │   ├── models.py             # SQLAlchemy models (deprecated notice)
│   │   ├── auth.py               # JWT auth (deprecated notice)
│   │   └── cache.py              # Redis caching
│   ├── ml/
│   │   ├── evaluation.py         # ML evaluation (CostOptimizer removed)
│   │   └── routing.py            # CostAwareRouter (trained classifier)
│   ├── eval/
│   │   ├── ragas_eval.py         # RAGAS evaluation (bigram + unigram heuristics)
│   │   ├── llm_judge.py          # NEW: LLM-as-Judge evaluation (minimax-m3)
│   │   ├── retrieval_metrics.py  # NDCG, MRR, Recall@K, Precision@K
│   │   └── golden_set.py         # Golden dataset for evaluation
│   ├── observability/
│   │   └── langfuse.py           # Langfuse integration (wired into graph)
│   ├── tasks/
│   │   └── celery_app.py         # Background tasks (deprecated notice)
│   └── ingestion/
│       ├── downloader.py         # EDGAR XBRL API
│       ├── parser.py             # Section-based chunking
│       └── pipeline.py           # Ingestion pipeline
├── scripts/
│   ├── ingest.py                 # Run ingestion
│   ├── evaluate.py               # Run evaluation
│   ├── evaluate_ml.py            # ML evaluation
│   ├── eval_ragas.py             # RAGAS evaluation
│   ├── eval_demo.py              # Demo evaluation (no external deps)
│   └── eval_llm_judge.py         # NEW: LLM-as-Judge evaluation (55 samples)
├── tests/
│   ├── conftest.py               # Pytest fixtures (mock_llm, mock_redis)
│   ├── test_config.py            # 5 basic tests
│   └── test_comprehensive.py     # 97 comprehensive tests
├── data/
│   ├── raw/                      # SEC filings
│   └── eval/                     # Evaluation results
│       ├── ragas_results.json    # Heuristic evaluation
│       ├── llm_judge_results.json # NEW: LLM-as-Judge evaluation
│       └── retrieval_metrics.json
├── docker-compose.yml            # Docker services
├── Dockerfile                    # API container
├── requirements.txt              # Python dependencies (ragas==0.4.3)
├── PLAN.md                       # Project plan
├── PROGRESS.md                   # This file
└── README.md                     # Project readme
```

---

## ROAST_REVIEW_V2 Fix Status

**Fixed**: 53/53 issues (deployment skipped per user request)

Score: **3.5/10 → 5/10 → ~8/10 → ~9/10** (with LLM-as-Judge evaluation)

---

## Evaluation Results

### LLM-as-Judge (minimax-m3:cloud) — 55 samples

| Metric | Score |
|--------|-------|
| Faithfulness | 0.60 |
| Answer Relevancy | 0.92 |
| Context Precision | 0.97 |
| Context Recall | 1.00 |
| **Overall** | **0.85** |

### Retrieval Metrics

| Metric | Score |
|--------|-------|
| NDCG@10 | 0.71 |
| MRR | 0.61 |
| Hit Rate | 1.00 |

### Comparison: Heuristic vs LLM Judge

| Metric | Heuristic | LLM Judge |
|--------|-----------|-----------|
| Faithfulness | 0.37 | 0.60 |
| Answer Relevancy | 0.26 | 0.92 |
| Context Precision | 0.18 | 0.97 |
| Context Recall | 0.41 | 1.00 |
| Overall | 0.30 | 0.85 |

---

## Open Issues

None — all roast review issues addressed. Cloud deployment skipped per user request.
