# Cost-Aware Agentic RAG - Project Plan

## Overview

Production-grade Agentic RAG system for SEC 10-K Financial Document Analysis.
Senior ML/AI Engineering Portfolio Project.

**Repository**: https://github.com/DeryFerd/cost-aware-agentic-rag

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Next.js 14)                            │
│   Dashboard | Documents | Analytics | Settings | Real-time Streaming       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY (FastAPI)                               │
│   Rate Limiting | Auth (JWT) | Caching (Redis) | WebSocket                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   Query Service     │  │  Ingestion Service  │  │  Analytics Service  │
│   - Orchestrator    │  │  - Pipeline         │  │  - Metrics          │
│   - Tool Calling    │  │  - Chunking         │  │  - Cost Tracking    │
│   - Reflection      │  │  - Embedding        │  │  - User Activity    │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
              │                       │                       │
              ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA LAYER                                        │
│   PostgreSQL (Metadata) | ChromaDB (Vectors) | Redis (Cache) | S3 (Files) │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ML/AI SERVICES                                      │
│   Ollama Cloud (LLM) | Sentence-Transformers | Docling | Vision Models     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 12: Data Expansion (Current)

### 12.1 Download More SEC Data
- [ ] Download 2025 10-K filings for all companies
- [ ] Add more companies: AAPL, NVDA, JPM, V, WMT
- [ ] Parse XBRL format (SEC new format)
- [ ] Extract structured financial data from XBRL
- [ ] Target: 500+ chunks from real data

### 12.2 Data Pipeline Improvements
- [ ] Async ingestion with Celery
- [ ] Incremental updates (only new filings)
- [ ] Data validation and quality checks
- [ ] Metadata enrichment (sector, industry)

---

## Phase 13: Backend Complexity

### 13.1 Database Layer (PostgreSQL)
- [ ] User model (authentication)
- [ ] Document model (filing metadata)
- [ ] Query model (history, feedback)
- [ ] Conversation model (multi-turn)
- [ ] Cost model (tracking, budgets)

### 13.2 Async Processing
- [ ] Celery workers for background tasks
- [ ] Redis for task queue
- [ ] Document ingestion jobs
- [ ] Batch query processing
- [ ] Scheduled re-indexing

### 13.3 Authentication & Authorization
- [ ] JWT authentication
- [ ] API key management
- [ ] Role-based access (admin, user)
- [ ] Rate limiting per user

### 13.4 Caching Layer
- [ ] Redis cache for frequent queries
- [ ] TTL-based invalidation
- [ ] Cache warming for common queries
- [ ] Cost optimization (skip LLM for cached)

### 13.5 Real-time Features
- [ ] WebSocket for streaming
- [ ] Server-Sent Events (SSE)
- [ ] Real-time cost updates
- [ ] Live query progress

---

## Phase 14: Frontend Complexity

### 14.1 Modern Stack
- [ ] Next.js 14 with App Router
- [ ] TypeScript for type safety
- [ ] Tailwind CSS + shadcn/ui
- [ ] React Query for data fetching

### 14.2 Interactive Features
- [ ] Real-time streaming responses
- [ ] Interactive financial charts (Recharts/D3.js)
- [ ] Document viewer with highlights
- [ ] Side-by-side comparison view
- [ ] Export to PDF/Excel

### 14.3 Dashboard Analytics
- [ ] Query volume charts
- [ ] Cost breakdown by model
- [ ] Company coverage heatmap
- [ ] Response time metrics
- [ ] User activity tracking

### 14.4 Document Management
- [ ] Upload custom documents
- [ ] Document metadata editor
- [ ] Chunk preview/edit
- [ ] Bulk operations

---

## Phase 15: ML/AI Engineering

### 15.1 Model Evaluation
- [ ] Automated test suite (100+ queries)
- [ ] Hallucination detection
- [ ] Factual accuracy scoring
- [ ] Response quality metrics
- [ ] A/B testing framework

### 15.2 Cost Optimization
- [ ] Query complexity classifier
- [ ] Model routing (4b vs 27b)
- [ ] Token budget management
- [ ] Cost prediction before query
- [ ] ROI analysis per query type

### 15.3 Retrieval Optimization
- [ ] Query expansion (HyDE)
- [ ] Semantic chunking
- [ ] Parent-child relationships
- [ ] Cross-encoder re-ranking
- [ ] ColBERT integration

### 15.4 Monitoring & Observability
- [ ] Prometheus metrics
- [ ] Grafana dashboards
- [ ] Distributed tracing (OpenTelemetry)
- [ ] Error tracking (Sentry)
- [ ] Performance profiling

---

## Phase 16: DevOps & Deployment

### 16.1 Containerization
- [ ] Docker Compose (all services)
- [ ] Multi-stage builds
- [ ] Health checks
- [ ] Volume management

### 16.2 Cloud Deployment
- [ ] Railway/Render deployment
- [ ] Environment variables
- [ ] Database hosting
- [ ] CDN for static assets

### 16.3 CI/CD
- [ ] GitHub Actions workflow
- [ ] Automated testing
- [ ] Linting (ruff, mypy)
- [ ] Security scanning
- [ ] Auto-deploy on merge

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Data Coverage | 500+ chunks, 8+ companies, 3+ years |
| Query Accuracy | 95%+ factual accuracy |
| Response Time | <3s for simple, <10s for complex |
| Cost Efficiency | <$0.01 per average query |
| Test Coverage | 80%+ code coverage |
| Uptime | 99.9% availability |

---

## Tech Stack

### Backend
- **Framework**: FastAPI (async)
- **Database**: PostgreSQL + SQLAlchemy
- **Cache**: Redis
- **Queue**: Celery + Redis
- **Vector DB**: ChromaDB
- **Search**: BM25 (rank_bm25)

### Frontend
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS + shadcn/ui
- **Charts**: Recharts / D3.js
- **State**: React Query + Zustand

### ML/AI
- **LLM**: Ollama Cloud (gemma3:4b, gemma3:27b)
- **Embeddings**: sentence-transformers all-MiniLM-L6-v2
- **Parser**: Docling (IBM)
- **Vision**: gemma3:27b

### DevOps
- **Container**: Docker + Docker Compose
- **CI/CD**: GitHub Actions
- **Monitoring**: Prometheus + Grafana
- **Tracing**: OpenTelemetry

---

## Timeline

| Week | Focus | Deliverables |
|------|-------|--------------|
| 1 | Data Expansion | 500+ chunks, 8 companies |
| 2 | Backend (DB, Auth, Async) | PostgreSQL, JWT, Celery |
| 3 | Frontend (Next.js) | Modern dashboard |
| 4 | ML Engineering | Evaluation, optimization |
| 5 | DevOps | Docker, CI/CD, deploy |
| 6 | Polish | Tests, docs, demo |
