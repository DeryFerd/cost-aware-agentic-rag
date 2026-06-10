# 🔥 PORTFOLIO ROAST: Cost-Aware Agentic RAG

### Perspective: Senior ML/AI Engineer reviewing a Junior's portfolio for 2026 hiring

---

> [!CAUTION]
> **Overall Verdict: 3.5/10 — This is a tutorial project in a trenchcoat pretending to be production-grade.**
> 
> Every buzzword in the title — "Cost-Aware", "Agentic", "Multimodal", "Production-Level" — is either a half-truth or an outright lie when you read the actual code. The PLAN.md and PROGRESS.md look impressive. The code tells a very different story.

---

## 📊 Scorecard

| Category | Score | Verdict |
|----------|-------|---------|
| **Architecture & Design** | 4/10 | Ambitious diagram, hollow implementation |
| **ML/AI Engineering** | 2/10 | Keyword matching disguised as ML |
| **Code Quality** | 3/10 | Tutorial-grade with production buzzwords |
| **Testing** | 1/10 | ONE test file. Testing config loading. |
| **DevOps/Infra** | 2/10 | Docker Compose that won't build |
| **Data Engineering** | 5/10 | The most genuine part |
| **Documentation** | 6/10 | Great at selling what doesn't exist |
| **Portfolio Readiness (2026)** | 3/10 | Would not pass senior review |

---

## 🚨 THE FATAL FLAWS

### 1. The "Agentic" System is an If-Else Loop

**Claim**: "True agentic system with tool calling, planning, reflection"

**Reality** ([orchestrator.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/agents/orchestrator.py)):

The "agentic" system is a `while` loop that:
1. Sends query to LLM
2. Checks if LLM output contains a tool call string
3. Executes the tool
4. Feeds result back to LLM
5. Repeat until LLM stops calling tools

That's it. That's **every LLM wrapper tutorial on YouTube since 2023**.

What's **missing** for a real agentic system in 2026:
- ❌ No planning step (ReAct, Plan-and-Execute, Tree of Thought)
- ❌ No reflection/self-correction (despite claiming it)
- ❌ No backtracking on failed tool calls
- ❌ No dynamic tool selection based on context
- ❌ No multi-agent coordination
- ❌ No state machine or graph-based orchestration (LangGraph, CrewAI, AutoGen patterns)

> [!WARNING]
> In 2026, calling a tool-calling loop "agentic" is like calling a calculator "AI". Every hiring manager who has used LangGraph or CrewAI will see through this in 30 seconds.

---

### 2. The "Cost-Aware Routing" is a 2-Line If-Statement

**Claim**: "Classifies query complexity and routes to appropriate (and cost-efficient) models"

**Reality** ([llm_client.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/generation/llm_client.py)):

```python
# The entire "cost-aware routing" is essentially:
if "compare" in query or "trend" in query:
    model = "gemma3:27b"  # complex
else:
    model = "gemma3:4b"   # simple
```

What this should be:
- A trained classifier (even a simple logistic regression) on query complexity
- Token-level cost estimation with actual API pricing
- Dynamic model selection based on budget constraints
- A/B testing framework for model quality vs. cost tradeoffs
- Bandit algorithms for online model selection

What it actually is: **keyword matching**. The word "compare" in your query triggers the big model. That's not ML engineering. That's string matching.

---

### 3. "98% Accuracy" is Self-Graded Nonsense

**Claim**: "Query Accuracy 98%, Evaluation (0.98/1.00 score)"

**Reality** ([evaluation.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/ml/evaluation.py)):

The system generates answers, then asks **the same LLM** to grade itself. This is like a student grading their own exam and reporting they got 98%.

What's missing:
- ❌ No human evaluation baseline
- ❌ No inter-annotator agreement
- ❌ No retrieval quality metrics (Recall@K, MRR, NDCG)
- ❌ No faithfulness grounding (is the answer actually supported by retrieved chunks?)
- ❌ No hallucination detection
- ❌ No comparison against baseline (no RAG vs. with RAG)
- ❌ No RAGAS, no DeepEval, no proper eval framework

> [!CAUTION]
> Putting "98% accuracy" on your resume from a self-graded LLM-as-judge evaluation with no human baseline is a **career-ending red flag** if a senior engineer digs into it. It screams "I don't understand evaluation".

---

### 4. "Multimodal" = One API Call

**Claim**: "Multimodal support (tables, vision, images)"

**Reality** ([vision.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/multimodal/vision.py), [tables.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/multimodal/tables.py)):

- "Vision support" = sending a base64 image to Ollama and asking "what do you see?"
- "Table extraction" = regex-based text parsing
- No cross-modal retrieval (text query → image results)
- No multi-modal embeddings (CLIP, SigLIP, ColPali)
- No visual document understanding pipeline
- No chart/graph extraction or understanding

In 2026, "multimodal RAG" means **ColPali/ColQwen for visual document retrieval**, **vision-language models with grounding**, and **cross-modal embedding spaces**. Not "I base64-encode a PNG and send it to an LLM".

---

### 5. The Entire Infrastructure is Dead Code

This is the most damaging finding:

| Component | Status | Evidence |
|-----------|--------|----------|
| **PostgreSQL** | 🪦 Dead code | Models defined, never used in query flow |
| **Redis Cache** | 🪦 Dead code | `cache.py` exists, never called |
| **JWT Auth** | 🪦 Dead code | `auth.py` exists, never enforced on routes |
| **Celery Tasks** | 🪦 Dead code | Tasks defined, never triggered |
| **Langfuse Observability** | 🪦 Empty dir | `src/observability/` is literally empty |
| **Rate Limiting** | 🪦 Never implemented | Mentioned in architecture, doesn't exist |

> [!IMPORTANT]
> **Phase 13 ("Backend Complexity: PostgreSQL, Redis, JWT, Celery") is fiction.** The files exist. They are never imported, never called, never tested. This is like listing "Kubernetes" on your resume because you have a YAML file.

---

### 6. Docker Compose Won't Even Build

The `docker-compose.yml` references `./frontend/Dockerfile` which **does not exist**. Running `docker-compose up` will fail immediately.

This means:
- Phase 16 ("DevOps: Docker Compose") was never actually tested
- The "production" system has never been run as advertised

---

### 7. ONE Test. Testing Config.

[test_config.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/tests/test_config.py) — 75 lines. Tests that the config loads.

That's the entire test suite. For a project claiming:
- Agentic orchestration
- Hybrid retrieval with fusion
- Cost-aware routing
- JWT authentication
- Multimodal processing
- 16 phases of development

**Estimated test coverage: 1-2%**. A "production" system needs 70%+ coverage minimum. This has one test that checks `config.model_name is not None`.

---

## 🔴 GIT HISTORY RED FLAGS

The entire git history reveals the truth:

```
June 6, 23:34  → "initial project structure with full Agentic RAG pipeline"
June 7, 00:26  → "working end-to-end Agentic RAG pipeline"  
June 9, 21:39  → "expand data to 7 companies, 2075 chunks"   (+3 lines)
June 9, 21:41  → "PostgreSQL, Redis, JWT auth, Celery tasks"  (7 files, 492 lines)
June 9, 21:48  → "Next.js 14 frontend"                        (22 files, 8097 lines)
June 9, 21:51  → "ML evaluation, cost optimization, Docker"   (6 files, 546 lines)
```

**492 lines for PostgreSQL + Redis + JWT + Celery in one commit.** That's ~120 lines per technology. You can't implement any of these properly in 120 lines — which confirms they're scaffolding, not implementation.

**8,097 lines of frontend in a single commit.** That's likely scaffolded/generated code.

**The entire "production" upgrade from Phase 12-16 happened in ~2 hours** (21:15 to 21:57 on June 9). Four major phases in 2 hours. Let that sink in.

---

## 🐛 SPECIFIC BUGS & CRASHES (Line-Level)

These are not "code smells" — these are **bugs that will crash the system or silently produce wrong results**.

| Severity | File | Line(s) | Bug Description |
|----------|------|---------|-----------------|
| 🔴 CRASH | [evaluation.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/ml/evaluation.py) | 120-129 | References 4 attributes that **don't exist** on `AgentResponse`: `tokens_input`, `tokens_output`, `cost_usd`, `context_data`. The `run_evaluation()` method will crash with `AttributeError` every time. **The eval pipeline has never been successfully run.** |
| 🔴 CRASH | [cache.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/database/cache.py) | 69, 75 | `datetime` is used but **never imported**. `get_cost_today()` and `add_cost()` will crash with `NameError` if ever called. |
| 🟡 LOGIC | [hybrid.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/retrieval/hybrid.py) | 142 | `meta` variable in reranking loop refers to the **last iteration** of the previous loop. Ticker/year boost is applied using ONE arbitrary document's metadata to ALL results. Corrupts reranking. |
| 🟡 LOGIC | [llm_client.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/generation/llm_client.py) | MODEL_COSTS | `MODEL_COSTS` contains `qwen3.5`, `deepseek-v4-flash`, `kimi-k2.6` — but config uses `gemma3:4b`/`gemma3:27b`. Models never match the cost table → `_estimate_cost` always returns **$0.00**. The entire cost tracking is silently broken. |
| 🟡 LOGIC | [orchestrator.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/agents/orchestrator.py) | 181 | `total_cost += 0.0` — literal no-op. Cost is never accumulated from LLM calls. `AgentResponse.total_cost_usd` is always 0. |
| 🟡 LOGIC | [orchestrator.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/agents/orchestrator.py) | 137 | `conv_context` computed but **NEVER USED**. Conversation history is fetched, assigned to a variable, then completely ignored. Multi-turn memory is dead. |
| 🟡 LOGIC | [vector_store.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/retrieval/vector_store.py) | IDs | `ids = [f"{ticker}_{i}" for ...]` — re-ingesting same ticker **overwrites** all previous documents. ID collision on every re-run. |
| 🟡 LOGIC | [orchestrator.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/agents/orchestrator.py) | _plan() | JSON parsing uses greedy `re.search(r'\{.*\}', ..., re.DOTALL)` — matches first `{` to LAST `}` in entire response. Captures garbage if LLM outputs multiple JSON blocks. |
| 🟠 DATA | Frontend [page.tsx](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/frontend/src/app/page.tsx) | fetch | Sends `{ question: userMessage }` but API expects `{ query: ... }` (`QueryRequest.query`). Field name mismatch → API will reject or ignore the input. |
| 🟠 SECURITY | [config.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/config.py) | 47 | `secret_key` defaults to `"your-secret-key-change-in-production"`. Hardcoded secret in source code. |
| 🟠 RUNTIME | [database/models.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/database/models.py) | import-time | `engine = create_engine(settings.database_url)` runs at **import time** — will crash if DB isn't reachable. Importing the module = requiring a live database. |
| 🟠 DEPS | requirements.txt | — | **Missing critical dependencies**: `celery`, `redis`, `sqlalchemy`, `python-jose`, `passlib` are all imported in code but NOT in requirements.txt. `pip install -r requirements.txt` will NOT install what the code needs. |

---

## 📋 PER-FILE CODE QUALITY BREAKDOWN

### Core ML/AI Layer

| File | Lines | Quality | Production? | Key Issue |
|------|-------|---------|-------------|-----------|
| [orchestrator.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/agents/orchestrator.py) | 468 | Plan→Execute→Reflect loop is real. Dead memory, zero cost, no max_iterations guard | ❌ | `conv_context` dead, `total_cost` always 0, no runaway protection |
| [tools.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/agents/tools.py) | 153 | Clean `ToolRegistry` class | 🪦 **DEAD** | Orchestrator defines its own `TOOLS` dict. This file is never imported. Two parallel tool systems. |
| [memory.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/agents/memory.py) | 86 | Clean dataclass, session management | 🪦 **DEAD** | Output is computed but never passed to any LLM prompt. Global singleton = not thread-safe. |
| [hybrid.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/retrieval/hybrid.py) | 165 | Genuine RRF fusion with score normalization | ⚠️ Buggy | `meta` variable scope corrupts reranking. "Re-ranking" is keyword overlap, not cross-encoder. |
| [vector_store.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/retrieval/vector_store.py) | 120 | Solid ChromaDB wrapper, lazy embedding | ⚠️ Near | ID collision on re-ingestion. No batch size limits. |
| [bm25_index.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/retrieval/bm25_index.py) | 88 | Clean minimal BM25 | ⚠️ Basic | Naive tokenizer (`text.lower().split()`), no stemming/stopwords. No metadata filtering (vector store has it, BM25 doesn't → fusion mixes filtered+unfiltered). |
| [llm_client.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/generation/llm_client.py) | 194 | Good design: complexity→routing→cost. Streaming + vision. | ❌ Broken | `MODEL_COSTS` doesn't match configured models → all costs = $0. No retry, no timeout, no fallback. |
| [cost_tracker.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/generation/cost_tracker.py) | 94 | Well-designed JSONL audit log pattern | 🪦 **DEAD** | `CostTracker.record()` is never called anywhere in the pipeline. Budget check only reports, never enforces. |
| [evaluation.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/ml/evaluation.py) | 265 | Word-overlap metrics, not ML evaluation | 💀 **BROKEN** | Will crash on any run (4 missing attributes). `CostOptimizer` duplicates `llm_client.py` with different hardcoded values. "HyDE" is a 3-entry synonym dict, not real HyDE. All costs = $0. |
| [tables.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/multimodal/tables.py) | 155 | Practical regex-based extraction | ✅ Adequate | Integrated into orchestrator. Only handles text-based tables, not PDF structures. |
| [vision.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/multimodal/vision.py) | 171 | Real vision pipeline: image→base64→LLM→parse | ✅ Adequate | `_parse_analysis()` is fragile regex on free-text LLM output. Hardcodes vision model without verifying it supports vision. |
| [images.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/multimodal/images.py) | 94 | Docling PDF extraction with error handling | ✅ Adequate | `hasattr(doc, "pictures")` suggests untested Docling API. Temp file cleanup could leak on process death. |
| [config.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/config.py) | 69 | Good 12-factor pattern with pydantic-settings | ✅ Good | Default `ollama_host` points to Ollama website, not a server. Hardcoded secret key. |

**Total Core: ~2,147 lines. ~30-40% is dead or broken code.**

### Infrastructure & API Layer

| File | Lines | Quality | Actually Used? | Key Issue |
|------|-------|---------|----------------|-----------|
| [api/main.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/api/main.py) | 260 | Functional FastAPI app with 8+ endpoints | ✅ Yes | CORS `allow_origins=["*"]`. No auth on any endpoint. Uses deprecated `@app.on_event`. Has a **third** web UI via Jinja2 templates (alongside Next.js AND Streamlit). |
| [api/models.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/api/models.py) | 52 | Clean Pydantic schemas | Partial | `DocumentInfo` and `EvalResultResponse` models defined but never used. |
| [database/models.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/database/models.py) | 164 | Well-structured SQLAlchemy with 7 models | 🪦 **DEAD** | Never imported by API. Default is SQLite despite docstring saying "PostgreSQL". No Alembic migrations. Crashes at import if DB unreachable. |
| [database/auth.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/database/auth.py) | 93 | Textbook JWT + bcrypt | 🪦 **DEAD** | No endpoint uses `Depends(get_current_user)`. 100% orphaned. |
| [database/cache.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/database/cache.py) | 83 | Redis wrapper with TTL, rate limiting | 🪦 **DEAD + BROKEN** | Never called. Also has `datetime` not imported → would crash if called. |
| [tasks/celery_app.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/tasks/celery_app.py) | 139 | 4 task definitions, Redis broker | 🪦 **DEAD** | No `task.delay()` anywhere. `cleanup_old_cache` is a stub with a comment "This would implement...". Not in requirements.txt. |
| [observability/langfuse.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/observability/langfuse.py) | 86 | Graceful opt-in Langfuse wrapper | ⚠️ Disabled | Empty keys in .env → always disabled. Not wired into query flow. |
| [ingestion/downloader.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/ingestion/downloader.py) | 162 | Real EDGAR XBRL API integration | ✅ Works | User-Agent has placeholder email. Rate limiting is just `time.sleep(0.25)`. |
| [ingestion/parser.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/ingestion/parser.py) | 161 | Regex section detection, sentence chunking | ✅ Works | Docstring says "using Docling" but **Docling is never actually called**. Just does `file.read_text()`. |
| [ingestion/pipeline.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/src/ingestion/pipeline.py) | 88 | Real glue code, functional | ✅ Works | No error recovery, no progress persistence, no Celery integration. |

### Frontend & DevOps

| File | Lines | Quality | Real? | Key Issue |
|------|-------|---------|-------|-----------|
| Frontend — [page.tsx](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/frontend/src/app/page.tsx) (Chat) | 283 | SSE streaming chat UI | ✅ Real | Field name mismatch: sends `{question}` not `{query}`. Hardcoded `localhost:8001`. |
| Frontend — [analytics/page.tsx](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/frontend/src/app/analytics/page.tsx) | 238 | Recharts dashboard | 🎭 **MOCKUP** | ALL stats hardcoded: "1,247 Total Queries", "$12.45 Total Cost". Zero API calls. Inline data arrays. |
| Frontend — [documents/page.tsx](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/frontend/src/app/documents/page.tsx) | 179 | Document list with filters | 🎭 **MOCKUP** | 20 documents hardcoded in `const documents = [...]`. Upload/View/Export buttons do nothing. Zero API calls. |
| Frontend — [Sidebar.tsx](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/frontend/src/components/Sidebar.tsx) | 70 | Nav sidebar | ✅ Real | — |
| [ci.yml](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/.github/workflows/ci.yml) | 28 | `pip install` + `pytest` | 🎭 **THEATER** | No lint, no typecheck, no Docker, no frontend. Installs PyTorch (~2GB) to run 5 trivial tests. Several tests will FAIL in CI (depend on local data). |
| [test_config.py](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/tests/test_config.py) | 87 | 5 trivial tests | ❌ Cosmetic | `test_retrieval_filters` tests a **locally-defined function**, not production code. No conftest.py, no fixtures, no mocking. |
| `src/dashboard/` | 0 | Empty `__init__.py` + empty dirs | 🪦 **EMPTY** | "Streamlit dashboard" = zero lines of dashboard code. Just empty directories. |
| [requirements.txt](file:///D:/Portfolio%20Data/Production-Level%20AI%20Projects/Agentic%20x%20Multimodal%20RAG/cost-aware-agentic-rag/requirements.txt) | 172 pkgs | `pip freeze` dump | ❌ Broken | Missing: celery, redis, sqlalchemy, jose, passlib. Includes Streamlit + Next.js (confused arch). Includes tree-sitter, kubernetes — likely unused. |

> [!WARNING]
> **Three separate UIs exist**: (1) Jinja2 templates served by FastAPI, (2) Next.js 14 frontend, (3) Streamlit dashboard (empty). This is architectural confusion, not "full-stack engineering". Pick ONE.

---

## 🟡 WHAT ACTUALLY WORKS (Credit Where Due)

1. **Data Ingestion** — Real SEC EDGAR data was downloaded and processed. 2,075 chunks from 7 companies. This is genuine work.
2. **Hybrid Retrieval** — RRF fusion between vector and BM25 is correctly implemented, even if basic.
3. **The Tool-Calling Loop** — It works. It answers financial questions. It's just not "agentic" in any meaningful sense.
4. **Project Structure** — The directory layout is clean and well-organized.
5. **README** — The documentation is professional (too professional for the code behind it).

---

## 🟢 2026 AI Engineer Portfolio: What's Actually Expected

In mid-2026, here's what a competitive AI Engineer portfolio needs:

### Must-Haves (Table Stakes)
| Requirement | Your Project | Gap |
|-------------|-------------|-----|
| Graph-based agent orchestration (LangGraph, CrewAI) | ❌ While loop | Critical |
| Proper eval framework (RAGAS, DeepEval, custom metrics) | ❌ Self-graded LLM | Critical |
| Real retrieval metrics (MRR, NDCG, Recall@K) | ❌ None | Critical |
| Modern embeddings (2024+ models, multi-vector) | ❌ MiniLM-v2 (2021) | Critical |
| Actual test coverage (>50%) | ❌ 1-2% | Critical |
| Working CI/CD that tests something | ❌ Tests config only | Major |
| Infrastructure that's actually wired up | ❌ Dead code | Major |

### Differentiators (Stand-Out)
- ColPali/ColQwen for visual document retrieval
- Fine-tuned embedding models for domain-specific retrieval
- Online evaluation with human feedback loops
- Actual cost optimization with learned routing (not if-else)
- Multi-agent collaboration patterns
- Guardrails and safety filters
- Streaming with structured output (tool calls via structured generation)
- Deployment with auto-scaling and monitoring

---

## 🛠️ UPGRADE ROADMAP (Priority Order)

### 🔴 P0 — Fix Before Anyone Sees This

1. **Delete dead code or wire it up**
   - Either integrate PostgreSQL/Redis/JWT/Celery into the actual flow, or remove them
   - Dead code is worse than no code — it signals dishonesty

2. **Fix Docker**
   - Create the missing `frontend/Dockerfile`
   - Actually test `docker-compose up` end-to-end
   - If it doesn't build, don't claim DevOps

3. **Fix the test suite**
   - Add unit tests for orchestrator, retrieval, tools
   - Add integration tests for the API
   - Target 50%+ coverage minimum
   - Make CI actually run lint + typecheck + tests

4. **Remove the "98% accuracy" claim**
   - Replace with honest RAGAS evaluation
   - Report retrieval metrics: Recall@5, MRR, NDCG
   - Report generation metrics: faithfulness, answer relevancy
   - Add human evaluation on 50 samples

### 🟡 P1 — Make It Actually Impressive

5. **Replace the tool-calling loop with LangGraph**
   - Implement a proper state graph with planning, execution, reflection nodes
   - Add conditional edges for retry/backtrack
   - This single change transforms the project from "tutorial" to "senior-level"

6. **Upgrade embeddings**
   - Use `nomic-embed-text-v1.5`, `bge-m3`, or `GTE-large` at minimum
   - Consider ColBERT or multi-vector retrieval for financial documents
   - 384-dim MiniLM in 2026 is a joke

7. **Implement real cost-aware routing**
   - Train a simple classifier on query complexity
   - Use actual token costs from Ollama/provider pricing
   - Implement budget-constrained optimization
   - Log and visualize cost vs. quality tradeoffs

8. **Make multimodal real**
   - ColPali for visual document retrieval
   - Structured table extraction with Docling's table models
   - Cross-modal retrieval benchmarks

### 🟢 P2 — Stand Out From the Crowd

9. **Add a proper observability stack**
   - Langfuse OR LangSmith actually integrated
   - Trace every query end-to-end: retrieval → generation → tool calls
   - Dashboard showing real metrics over time

10. **Implement guardrails**
    - Input validation (prompt injection detection)
    - Output validation (factual grounding checks)
    - PII detection and redaction

11. **Add online evaluation**
    - User feedback collection (thumbs up/down)
    - Automatic regression detection
    - A/B testing framework for model changes

12. **Deploy for real**
    - Railway/Render/Fly.io with actual URL
    - Live demo that a recruiter can click
    - Monitoring and alerting

---

## 💀 FINAL ROAST

This project is a **speed-run of buzzwords**. You built a working RAG pipeline in ~3 days (June 6-9), which is genuinely impressive velocity. But then you spent the last 2 hours of day 3 frantically adding PostgreSQL, Redis, JWT, Celery, Next.js, Docker, and evaluation — none of which are actually connected to anything.

The result is a project that looks like a senior engineer's system from the `README.md` but reads like a bootcamp final project from the `src/` directory.

**The saddest part?** The core RAG pipeline (ingestion → hybrid retrieval → generation) actually works and answers real financial questions. If you had spent those 2 hours writing tests and polishing the core instead of stapling on dead infrastructure, you'd have a much stronger portfolio piece.

> **In hiring, we don't read READMEs. We read code. And this code tells us you prioritized looking impressive over being impressive.**

The good news: the foundation is real, the domain is relevant, and the problems are fixable. But right now, this portfolio piece would get you a "no" from any team with a senior ML engineer doing the code review.

**Fix the P0s. Then the P1s. Then you'll have something worth showing.**
