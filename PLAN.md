# Cost-Aware Agentic RAG - Project Plan

## Overview

Production-grade Agentic RAG system for SEC 10-K Financial Document Analysis with Cost-Aware Model Routing.

**Repository**: https://github.com/DeryFerd/cost-aware-agentic-rag

---

## Goals

- Build a portfolio-worthy AI Engineering project
- Demonstrate Agentic RAG, cost-aware routing, hybrid retrieval, and production observability
- Target: AI Engineer job interviews in 2026

---

## Architecture

```
User Query → Complexity Router → Model Selection → Retrieval → LLM Generation → Response
                                ↓
                    ┌───────────────────────┐
                    │   Hybrid Retriever     │
                    │   Vector + BM25        │
                    └───────────────────────┘
                                ↓
                    ┌───────────────────────┐
                    │   Ollama Cloud         │
                    │   gemma3:4b / 27b      │
                    └───────────────────────┘
```

---

## Tech Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| LLM Runtime | Ollama Cloud | Free tier, same API as local |
| Document Parser | Docling (IBM) | 97.9% table accuracy, MIT |
| Embeddings | sentence-transformers | Local, no API cost |
| Vector Store | ChromaDB | Simple, production-ready |
| Sparse Retrieval | BM25 (rank_bm25) | Complementary to vectors |
| API Framework | FastAPI | Async, auto-docs |
| Web Frontend | HTML/Tailwind/JS | SaaS-style, no framework |
| Dashboard | Streamlit | Quick data viz |
| Observability | Langfuse (planned) | Free, production-grade |
| Eval | LLM-as-judge | Best quality signal |

---

## Implementation Phases

### Phase 1: Data Foundation ✅
- SEC EDGAR scraper for 10-K filings
- Docling parser with HybridChunker
- ChromaDB vector store
- BM25 sparse index
- Ingestion pipeline orchestration

### Phase 2: Retrieval Engine ✅
- Hybrid fusion (vector + BM25)
- Score normalization
- Multi-index search

### Phase 3: Agentic Orchestration ✅
- Ollama Cloud client
- Complexity router (simple/complex)
- Answer generation with context
- Response cleanup (tool syntax removal)

### Phase 4: Web Application ✅
- Landing page (hero, features, CTA)
- Dashboard (chat interface, real-time stats)
- Dark mode glassmorphism design
- Responsive layout

### Phase 5: API & Deployment ✅
- FastAPI REST endpoints
- Dockerfile + docker-compose
- Health check & cost tracking

### Phase 6: Evaluation Harness (Planned)
- Golden set of Q&A pairs
- LLM-as-judge evaluation
- Faithfulness, relevancy, completeness metrics
- Regression detection

### Phase 7: Observability (Planned)
- Langfuse integration
- Per-query cost tracking
- Quality metrics dashboard
- Model usage analytics

### Phase 8: Polish (Planned)
- Comprehensive tests
- CI/CD pipeline
- Documentation
- Performance optimization

---

## Key Decisions

| Decision | Choice | AlTERNATIVE |
|----------|--------|-------------|
| Dataset | SEC 10-K | Custom PDFs |
| LLM Runtime | Ollama Cloud | OpenAI API |
| Embeddings | Local (sentence-transformers) | Ollama Cloud (not supported) |
| Parser | Docling | Marker, LlamaParse |
| Frontend | Vanilla JS + Tailwind | React/Next.js |

---

## Open Issues

1. **Retrieval quality**: Some queries retrieve wrong documents (e.g., Microsoft revenue picking up Tesla data)
2. **No real SEC data**: Currently using sample documents
3. **No evaluation harness**: Need golden set + LLM-as-judge
4. **No Langfuse**: Observability not integrated yet
5. **No tests**: Need unit + integration tests
