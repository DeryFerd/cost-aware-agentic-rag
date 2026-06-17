# Cost-Aware Agentic RAG

Production-grade Agentic RAG system for SEC 10-K Financial Document Analysis with cost-aware model routing. Uses a trained ML classifier to route queries by complexity, hybrid retrieval with RRF fusion, cross-encoder reranking, and a LangGraph-based agentic loop with self-reflection.

## Architecture

```
                            ┌──────────────────────────────┐
                            │        User Query             │
                            └──────────────┬───────────────┘
                                           │
                            ┌──────────────▼───────────────┐
                            │   Query Processor             │
                            │   Rewriting + HyDE + Multi-   │
                            │   Query Expansion             │
                            └──────────────┬───────────────┘
                                           │
                            ┌──────────────▼───────────────┐
                            │   Cost-Aware Router           │
                            │   TF-IDF + LogisticRegression │
                            │   ┌─────────┬───────────┐     │
                            │   │ simple  │ complex   │     │
                            │   └────┬────┴─────┬─────┘     │
                            │        │          │           │
                            └────────┼──────────┼───────────┘
                                     │          │
                        ┌────────────▼──┐  ┌────▼────────────┐
                        │ gemma3:4b     │  │ gemma3:27b       │
                        │ (fast + cheap)│  │ (capable + vision)│
                        └────────────┬──┘  └────┬────────────┘
                                     │          │
                                     └─────┬────┘
                                           │
                            ┌──────────────▼───────────────┐
                            │   LangGraph Agent Loop        │
                            │                              │
                            │  ┌─────────┐ ┌────────────┐  │
                            │  │ Planner │─▶│ Tool Exec  │  │
                            │  └─────────┘ └─────┬──────┘  │
                            │                    │         │
                            │  ┌─────────────────▼───────┐ │
                            │  │     Hybrid Retriever     │ │
                            │  │  ┌───────┐ ┌──────────┐ │ │
                            │  │  │Vector │ │  BM25     │ │ │
                            │  │  │Chroma │ │  +stem    │ │ │
                            │  │  └───┬───┘ └────┬─────┘ │ │
                            │  │      └────┬─────┘       │ │
                            │  │      RRF Fusion (k=60)  │ │
                            │  │           │             │ │
                            │  │  Cross-Encoder Rerank   │ │
                            │  │  (ms-marco-MiniLM)      │ │
                            │  └───────────┬─────────────┘ │
                            │              │               │
                            │  ┌───────────▼─────────────┐ │
                            │  │     Generator            │ │
                            │  │  (context + query → LLM) │ │
                            │  └───────────┬─────────────┘ │
                            │              │               │
                            │  ┌───────────▼─────────────┐ │
                            │  │     Reflector            │ │
                            │  │  (self-evaluate → retry) │ │
                            │  └───────────┬─────────────┘ │
                            └──────────────┬───────────────┘
                                           │
                            ┌──────────────▼───────────────┐
                            │   Response + Citations        │
                            └──────────────────────────────┘
```

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| LLM (simple) | Ollama Cloud — `gemma3:4b` | Fast factual queries |
| LLM (complex) | Ollama Cloud — `gemma3:27b` | Multi-hop reasoning, vision |
| LLM (judge) | Ollama Cloud — `minimax-m3:cloud` | LLM-as-Judge evaluation |
| Embeddings | `BAAI/bge-small-en-v1.5` (384d, local) | Dense retrieval vectors |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` (local) | Precision reranking |
| Vector DB | ChromaDB (PersistentClient) | Document storage + cosine search |
| Sparse Retrieval | `rank_bm25` with stemming + stopwords | BM25 keyword matching |
| Fusion | Reciprocal Rank Fusion (RRF, k=60) | Score-agnostic list merging |
| Query Processing | Rule-based rewriting + HyDE + multi-query expansion | Recall improvement |
| Knowledge Graph | NetworkX | Entity/relation extraction |
| Routing Classifier | TF-IDF + LogisticRegression (sklearn) | Complexity classification |
| Agent Framework | LangGraph with self-reflection loop | Multi-step orchestration |
| API | FastAPI (30+ endpoints) | REST + SSE streaming |
| Frontend | Jinja2 HTML (9 pages) served by FastAPI | Web dashboard |
| Auth | bcrypt password hashing (file-based) | Admin access control |
| Cache | Redis (optional) | Query result + rate-limit caching |
| Observability | Langfuse | Per-query tracing |
| Evaluation | Golden set (55+ Q&A), LLM-as-Judge, retrieval metrics, CI gating | Quality assurance |
| Containerization | Docker Compose (api + redis) | Deployment |

## Archived Frontends

> **Note**: The `frontend-archived/` (Next.js) and `dashboard-archived/` (Streamlit) directories contain previous frontend implementations that are no longer actively maintained. The Jinja2-based web dashboard (`web/templates/`) is the primary and only supported frontend.

## Features

### Cost-Aware Routing
A trained `TF-IDF + LogisticRegression` classifier determines query complexity. Simple factual queries (`"What was Microsoft's revenue?"`) route to `gemma3:4b` for speed and low cost. Complex multi-hop queries (`"Compare Microsoft and Amazon revenue growth"`) route to `gemma3:27b`. Falls back to LLM-based classification when classifier confidence is below 0.6.

### Hybrid Retrieval
Parallel dense (ChromaDB cosine) and sparse (BM25) retrieval with automatic ticker/year filter extraction from the query. BM25 uses a custom Porter-like stemmer with English stopword removal.

### Reciprocal Rank Fusion
Score-agnostic RRF combines vector and BM25 ranked lists using `score = Σ 1/(k + rank)` with `k=60`. This avoids the need to normalize scores between heterogeneous retrieval methods.

### Cross-Encoder Reranking
After RRF fusion, a `cross-encoder/ms-marco-MiniLM-L-6-v2` model reranks the top candidates for precision. This provides a significant quality improvement over embedding-only similarity.

### Query Processing
Three-stage query transformation before retrieval:
1. **Rewriting**: pronoun resolution, abbreviation expansion, context addition
2. **HyDE**: generates a hypothetical answer paragraph and retrieves with that embedding
3. **Multi-Query Expansion**: generates 3 alternative phrasings for better recall

### LangGraph Agentic Loop
A four-node state graph (`planner → tools → generator → reflector`) with conditional edges. The reflector self-evaluates answer quality and can trigger a retry (up to 2 reflections).

### Knowledge Graph
NetworkX-based entity and relation extraction from SEC filings. Extracts companies, monetary values, dates, metrics, and persons using regex patterns. Builds knowledge triples (e.g., `Microsoft → REPORTED_REVENUE → $245.1 billion`).

### Evaluation Pipeline
- **Golden Set**: 76 curated Q&A pairs across MSFT, AMZN, TSLA, GOOG, META, AAPL, NVDA
- **LLM-as-Judge**: `minimax-m3:cloud` scores faithfulness, answer relevancy, context precision, context recall
- **Retrieval Metrics**: NDCG@10, MRR, Recall@5, Recall@10, Precision@5, Precision@10, Hit Rate
- **CI Gating**: configurable thresholds that gate deployment based on evaluation scores

## Quick Start

### 1. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Ollama API key:
#   OLLAMA_API_KEY=your_key_here
#   ADMIN_USERNAME=admin
#   ADMIN_PASSWORD=your_password_here
```

### 3. Ingest SEC 10-K Data

```bash
python scripts/ingest.py
```

### 4. Train Query Classifier

```bash
python -c "from src.ml.routing import train_classifier; train_classifier()"
```

### 5. Run API Server

```bash
uvicorn api.main:app --reload --port 8001
```

The dashboard is available at `http://localhost:8001/`.

### 6. Docker Deployment

```bash
docker compose up --build
```

This starts the API on port `8001` and Redis on port `6379`.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System health + document/chunk counts |
| POST | `/query` | Execute a financial query |
| POST | `/query/stream` | SSE streaming response |
| GET | `/cost/summary` | Cost analytics summary |
| GET | `/cost/budget` | Budget check |
| GET | `/documents` | List all indexed 10-K filings |
| POST | `/upload` | Upload PDF for indexing |
| GET | `/upload/status/{id}` | Upload processing status |
| GET | `/analytics/models` | Model cost/performance comparison |
| GET | `/analytics/routing` | Routing efficiency breakdown |
| GET | `/analytics/trend` | Cost trend over time |
| POST | `/feedback` | Submit query feedback |
| GET | `/feedback/stats` | Aggregated feedback stats |
| POST | `/eval/run` | Run evaluation on Q&A pair |
| GET | `/eval/averages` | Average evaluation scores |
| GET | `/knowledge/stats` | Knowledge graph stats |
| POST | `/knowledge/extract` | Extract entities from text |
| GET | `/suggestions` | Query suggestions |
| GET | `/anomalies` | Anomaly detection |
| POST | `/admin/login` | Admin login |
| GET | `/admin/users` | List users |
| GET | `/export/query` | Export query to PDF |
| GET | `/export/queries/csv` | Export history to CSV |
| GET | `/conversation/history` | Conversation history |

## Web Pages

| Path | Page |
|------|------|
| `/` | Landing page |
| `/app` | Main query dashboard |
| `/app/documents` | Document browser |
| `/app/analytics` | Cost analytics |
| `/app/comparison` | Model comparison |
| `/app/upload` | Document upload |
| `/app/latency` | Latency dashboard |
| `/app/cost-optimization` | Cost optimization |
| `/app/admin` | Admin panel |

## Project Structure

```
cost-aware-agentic-rag/
├── api/
│   ├── main.py              # FastAPI app + all routes
│   └── models.py            # Pydantic request/response models
├── src/
│   ├── config.py            # pydantic-settings config (all paths, models, etc.)
│   ├── agents/
│   │   ├── graph.py         # LangGraph state graph + orchestrator
│   │   ├── memory.py        # Conversation memory (multi-turn)
│   │   └── guardrails.py    # Input/output guardrails
│   ├── retrieval/
│   │   ├── vector_store.py  # ChromaDB + bge-small-en embeddings
│   │   ├── bm25_index.py    # BM25 with stemming + stopwords
│   │   ├── fusion.py        # RRF + weighted score fusion
│   │   ├── hybrid.py        # HybridRetriever (vector + BM25 + RRF + rerank)
│   │   └── reranker.py      # Cross-encoder reranking
│   ├── generation/
│   │   ├── llm_client.py    # Ollama Cloud client + cost estimation
│   │   ├── cost_tracker.py  # Per-query cost tracking
│   │   └── prompts.py       # Prompt templates
│   ├── ml/
│   │   ├── routing.py       # TF-IDF + LogisticRegression classifier
│   │   ├── query_processor.py # Rewriting, HyDE, multi-query expansion
│   │   ├── cost_analytics.py # Model/routing cost analytics
│   │   ├── feedback.py      # User feedback storage
│   │   ├── suggestions.py   # Query suggestion engine
│   │   ├── anomaly.py       # Anomaly detection
│   │   └── export.py        # PDF/CSV export
│   ├── knowledge/
│   │   └── graph.py         # NetworkX knowledge graph + entity extraction
│   ├── multimodal/
│   │   ├── vision.py        # Image understanding (gemma3:27b)
│   │   ├── tables.py        # Table extraction from text
│   │   └── images.py        # Image processing
│   ├── eval/
│   │   ├── golden_set.py    # Golden Q&A set (55+ pairs)
│   │   ├── evaluator.py     # Evaluation runner
│   │   ├── llm_judge.py     # LLM-as-Judge (faithfulness, relevancy, etc.)
│   │   ├── retrieval_metrics.py # NDCG, MRR, Recall, Precision, Hit Rate
│   │   ├── pipeline.py      # EvalPipeline + CI Gating
│   │   └── ragas_eval.py    # RAGAS integration
│   ├── ingestion/
│   │   ├── downloader.py    # SEC EDGAR document downloader
│   │   ├── parser.py        # Document parser
│   │   ├── chunker.py       # Text chunking
│   │   ├── pipeline.py      # Ingestion pipeline
│   │   └── upload_handler.py # Upload processing
│   ├── database/
│   │   ├── admin_auth.py    # bcrypt auth, file-based sessions
│   │   ├── cache.py         # Redis caching layer
│   │   └── models.py        # SQLAlchemy models
│   ├── observability/
│   │   └── langfuse.py      # Langfuse integration
│   └── tasks/
│       └── celery_app.py    # Celery task queue
├── web/
│   ├── templates/           # Jinja2 HTML (9 pages)
│   │   ├── index.html       # Landing
│   │   ├── app.html         # Query dashboard
│   │   ├── documents.html   # Document browser
│   │   ├── analytics.html   # Cost analytics
│   │   ├── comparison.html  # Model comparison
│   │   ├── upload.html      # Upload page
│   │   ├── latency.html     # Latency dashboard
│   │   ├── cost_optimization.html # Cost optimization
│   │   └── admin.html       # Admin panel
│   └── static/              # CSS + JS
├── frontend-archived/        # Next.js frontend (archived)
├── dashboard-archived/       # Streamlit dashboard (archived)
├── scripts/
│   ├── ingest.py            # Data ingestion CLI
│   ├── evaluate.py          # Evaluation runner
│   ├── evaluate_ml.py       # ML evaluation
│   ├── eval_llm_judge.py    # LLM judge evaluation
│   ├── eval_ragas.py        # RAGAS evaluation
│   └── create_samples.py    # Sample data creation
├── tests/
│   ├── conftest.py          # Test fixtures
│   ├── test_comprehensive.py
│   └── test_config.py
├── data/
│   ├── raw/                 # Raw SEC filings (per ticker/year)
│   ├── processed/           # Parsed + chunked data
│   ├── indexes/             # ChromaDB + BM25 indices
│   └── eval/                # Golden set + eval results
├── docker-compose.yml       # api + redis
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

## Architecture Decision Records

### Why ChromaDB over Pinecone/Weaviate?
ChromaDB runs fully embedded with zero infrastructure. `PersistentClient` gives us disk-backed storage with HNSW indexing — no server process needed. For a single-tenant RAG system analyzing SEC filings, the scaling limits of ChromaDB are irrelevant, and the operational simplicity is a major win. The cosine similarity search with metadata filtering covers our exact use case (filter by ticker + year).

### Why Ollama Cloud over OpenAI/Anthropic?
Ollama Cloud provides access to open-weight models (`gemma3:4b`, `gemma3:27b`) with a unified API. The `gemma3:4b` model handles 80%+ of queries (simple factual lookups) at a fraction of the cost, while `gemma3:27b` provides strong reasoning and vision capabilities for complex multi-hop analysis. The Ollama client library (`ollama` pip package) is thin and well-maintained.

### Why RRF over Weighted Score Fusion?
Reciprocal Rank Fusion operates on rank positions, not raw scores. This is critical when fusing heterogeneous retrieval methods (cosine similarity from vector DB vs. BM25 log-odds scores) whose score distributions are not comparable. RRF with `k=60` is the standard from the original RRF paper and requires no weight tuning — a significant advantage over weighted fusion which needs per-dataset calibration.

### Why BGE-small-en-v1.5 over OpenAI Ada/large models?
`BAAI/bge-small-en-v1.5` produces 384-dimensional embeddings locally with no API calls. At 33M parameters it loads in under 2 seconds and encodes batches in milliseconds. On MTEB benchmarks it punches well above its size class. For SEC 10-K retrieval where the query-document semantic gap is narrow (financial terminology is consistent), the quality difference vs. larger models is negligible, while the latency and cost savings are substantial.

### Why TF-IDF + LogisticRegression for Routing?
A trained classifier on labeled query data (`TRAINING_DATA` in `src/ml/routing.py`) provides fast, deterministic routing with interpretable confidence scores. TF-IDF features capture the lexical patterns that distinguish simple lookups ("What is X's revenue?") from complex analysis ("Compare X and Y's risk factors across 3 years"). When confidence drops below 0.6, the system falls back to LLM-based classification — a hybrid approach that balances speed and accuracy.

### Why LangGraph over Raw LLM Calls?
LangGraph provides explicit state management, conditional edges, and checkpointing for the agent loop. The `planner → tools → generator → reflector` graph with a retry edge from reflector back to tools is natural to express as a state graph. `MemorySaver` checkpointing enables conversation continuity. The alternative (manually chaining LLM calls with if/else logic) would be harder to debug, extend, and observe.

## Evaluation Results

Run the full evaluation suite:

```bash
# LLM-as-Judge evaluation
python scripts/eval_llm_judge.py

# Retrieval metrics
python scripts/evaluate_ml.py

# RAGAS evaluation
python scripts/eval_ragas.py
```

### LLM-as-Judge Metrics (`minimax-m3:cloud` judge, 55 samples)

| Metric | Score |
|--------|-------|
| Faithfulness | 0.596 |
| Answer Relevancy | 0.918 |
| Context Precision | 0.975 |
| Context Recall | 1.000 |
| Overall (weighted) | 0.849 |

### Retrieval Metrics

| Metric | Score |
|--------|-------|
| NDCG@10 | 0.710 |
| MRR | 0.611 |
| Hit Rate | 1.000 |

### CI Gating Thresholds

| Metric | Threshold |
|--------|-----------|
| Overall Score | ≥ 0.6 |
| Retrieval Precision | ≥ 0.5 |
| Retrieval Recall | ≥ 0.5 |
| Answer Faithfulness | ≥ 0.6 |
| Answer Relevance | ≥ 0.5 |

## Example Queries

```bash
# Simple factual lookup (routes to gemma3:4b)
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What was Microsoft'\''s total revenue in 2024?"}'

# Complex comparison (routes to gemma3:27b)
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare Microsoft and Amazon revenue growth over the last 3 years"}'

# Streaming response
curl -X POST http://localhost:8001/query/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "What are Tesla'\''s main risk factors?"}'
```

## License

MIT
