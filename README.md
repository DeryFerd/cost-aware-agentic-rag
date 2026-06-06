# Cost-Aware Agentic RAG

Production-grade Agentic RAG system for SEC 10-K Financial Document Analysis with Cost-Aware Model Routing.

## Architecture

```
User Query → Complexity Router → Model Selection → Tool-Calling Agent → Response
                                ↓
                    ┌───────────────────────┐
                    │   Hybrid Retriever     │
                    │   Vector + BM25        │
                    └───────────────────────┘
                                ↓
                    ┌───────────────────────┐
                    │   Ollama Cloud         │
                    │   qwen3.5 / deepseek   │
                    └───────────────────────┘
```

## Features

- **Cost-Aware Routing**: Classifies query complexity and routes to appropriate (and cost-efficient) models
- **Hybrid Retrieval**: Vector similarity + BM25 sparse search with score fusion
- **Agentic Tool-Calling**: Multi-step reasoning with retrieve, summarize, compare, and cite tools
- **Evaluation Harness**: LLM-as-judge evaluation with faithfulness, relevancy, and completeness metrics
- **Full Observability**: Langfuse integration + per-query cost tracking
- **API-First**: FastAPI REST endpoints
- **Interactive Dashboard**: Streamlit-based visualization

## Tech Stack

| Component | Technology |
|-----------|------------|
| Document Parsing | Docling (IBM) |
| Embeddings | Ollama (nomic-embed-text) |
| Vector Store | ChromaDB |
| Sparse Retrieval | BM25 (rank_bm25) |
| LLM Runtime | Ollama Cloud |
| API Framework | FastAPI |
| Dashboard | Streamlit |
| Observability | Langfuse |

## Quick Start

### 1. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Ollama API key
```

### 3. Ingest SEC 10-K Data

```bash
python scripts/ingest.py
```

### 4. Run API Server

```bash
uvicorn api.main:app --reload --port 8000
```

### 5. Launch Dashboard

```bash
streamlit run dashboard/app.py
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System health check |
| POST | `/query` | Execute a financial query |
| GET | `/cost/summary` | Cost analytics summary |
| GET | `/cost/budget` | Budget check |

## Example Query

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What was Microsoft'\''s total revenue in 2024?"}'
```

## Project Structure

```
src/
├── ingestion/      # SEC EDGAR downloader + Docling parser
├── retrieval/      # Vector store + BM25 + hybrid fusion
├── agents/         # Tool-calling orchestrator
├── generation/     # Ollama Cloud client + cost tracking
├── eval/           # Golden set + LLM-as-judge
└── dashboard/      # Streamlit UI
api/                # FastAPI REST endpoints
scripts/            # CLI utilities
tests/              # Test suite
```

## License

MIT
