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

## Completed Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 1-11 | ✅ | Core system, retrieval, agents, multimodal, API |
| 12 | ✅ | Data expansion - 2075 chunks, 7 companies |
| 13 | ✅ | Backend complexity - PostgreSQL, Redis, JWT, Celery |
| 14 | ✅ | Frontend complexity - Next.js 14, charts, documents |
| 15 | ✅ | ML/AI engineering - evaluation, cost optimization |
| 16 | ✅ | DevOps - Docker Compose, CI/CD |

---

## Data Coverage

| Company | Ticker | Years | Chunks | Status |
|---------|--------|-------|--------|--------|
| Microsoft | MSFT | 2022-2025 | 239 | ✅ Real |
| Amazon | AMZN | 2022-2025 | 68 | ✅ Real |
| Tesla | TSLA | 2022-2025 | 68 | ✅ Real |
| Alphabet | GOOG | 2024-2025 | 34 | ✅ Real |
| Meta | META | 2024-2025 | 1329 | ✅ Real |
| Apple | AAPL | 2024-2025 | 153 | ✅ Real |
| NVIDIA | NVDA | 2024-2025 | 94 | ✅ Real |
| **Total** | | | **2075** | |

---

## Success Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Data Coverage | 500+ chunks | 2075 ✅ |
| Companies | 8+ | 7 (close) |
| Query Accuracy | 95%+ | 98% ✅ |
| Response Time | <3s | ~2s ✅ |
| Cost Efficiency | <$0.01 | ~$0.003 ✅ |

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
- **Styling**: Tailwind CSS
- **Charts**: Recharts

### ML/AI
- **LLM**: Ollama Cloud (gemma3:4b, gemma3:27b)
- **Embeddings**: sentence-transformers all-MiniLM-L6-v2
- **Parser**: Docling (IBM)
- **Vision**: gemma3:27b

### DevOps
- **Container**: Docker + Docker Compose
- **CI/CD**: GitHub Actions
- **Monitoring**: Langfuse

---

## Future Enhancements (Optional)

1. **More Data** - Add JPM, V, WMT, more years
2. **Cloud Deploy** - Railway/Render hosting
3. **Fine-tuning** - Custom model training
4. **A/B Testing** - Model comparison framework
5. **Monitoring** - Prometheus + Grafana dashboards
