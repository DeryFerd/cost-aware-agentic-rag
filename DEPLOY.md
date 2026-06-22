# Deployment Guide

## Required Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OLLAMA_HOST` | **Yes** | `https://ollama.com` | Ollama Cloud server URL |
| `OLLAMA_API_KEY` | **Yes** | — | Ollama Cloud API key |
| `ADMIN_USERNAME` | Docker / Admin panel | — | Admin panel login username |
| `ADMIN_PASSWORD` | Docker / Admin panel | — | Admin panel login password |
| `SECRET_KEY` | Docker only | — | Session signing key (any random string) |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis URL for caching |
| `LANGFUSE_PUBLIC_KEY` | No | — | Langfuse tracing public key |
| `LANGFUSE_SECRET_KEY` | No | — | Langfuse tracing secret key |
| `LANGFUSE_HOST` | No | `https://cloud.langfuse.com` | Langfuse instance URL |
| `API_HOST` | No | `0.0.0.0` | API bind address |
| `API_PORT` | No | `8000` | API port (overridden by Docker to `8001`) |

> **Note:** The Docker Compose file overrides the port to `8001`. When running locally with `uvicorn`, specify `--port 8001` to match.

## Quick Start (Local Development)

```bash
# 1. Clone the repo
git clone <repo-url>
cd cost-aware-agentic-rag

# 2. Create .env from the example
cp .env.example .env
# Edit .env and set at minimum:
#   OLLAMA_API_KEY=your_key_here
#   ADMIN_USERNAME=admin
#   ADMIN_PASSWORD=your_password_here

# 3. Install dependencies
pip install -r requirements.txt

# 4. Ingest SEC 10-K data (downloads + indexes)
python scripts/ingest.py

# 5. Start the API server
uvicorn api.main:app --reload --port 8001

# 6. Open the dashboard
# http://localhost:8001/
```

## Docker Deployment

```bash
# 1. Set env vars in .env
cp .env.example .env
# Edit .env — SECRET_KEY is required for Docker:
#   SECRET_KEY=<any-random-string>
#   ADMIN_USERNAME=admin
#   ADMIN_PASSWORD=your_password_here
#   OLLAMA_API_KEY=your_key_here

# 2. Build and start
docker compose up -d

# 3. Verify health
curl http://localhost:8001/health

# 4. View logs
docker compose logs -f api
```

The `data/` directory is mounted as a volume, so ingested indexes persist across restarts.

## Env Validation Script

Run `scripts/validate_env.py` before deploying to catch configuration issues early:

```bash
python scripts/validate_env.py
```

It checks:

- All required env vars are set
- Ollama server is reachable at `OLLAMA_HOST`
- Redis is reachable at `REDIS_URL` (if set)
- Data directories (`data/raw`, `data/processed`, `data/indexes`) exist

Exits with code 1 if any required check fails.

## Known Limitations

- **Cost model is approximate** — Token costs use per-million-token rates from public Ollama pricing. Actual costs may vary by deployment.
- **Upload status is in-memory** — Server restart loses pending upload status. Production would use persistent queue.
- **File-based auth** — Admin users and sessions stored in JSON files. Suitable for demo, not enterprise multi-tenant.
- **Single-process retrieval** — No distributed search or horizontal scaling. ChromaDB and BM25 are local.
- **Eval harness is offline** — Golden set has limited entries. Online eval with production traffic not yet implemented.
- **Agent loop is bounded** — Max 2 reflection iterations. No human-in-the-loop approval or tool budget enforcement.
- **No persistent deployment** — Docker builds locally. No cloud deployment, load balancer, or auto-scaling.
