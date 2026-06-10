"""Central configuration using pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Paths ────────────────────────────────────────────────────────
    project_root: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = project_root / "data"
    raw_dir: Path = data_dir / "raw"
    processed_dir: Path = data_dir / "processed"
    indexes_dir: Path = data_dir / "indexes"
    eval_dir: Path = data_dir / "eval"

    # ── Ollama Cloud ────────────────────────────────────────────────
    ollama_host: str = "https://ollama.com"
    ollama_api_key: str = ""
    ollama_simple_model: str = "gemma3:4b"
    ollama_complex_model: str = "gemma3:27b"

    # ── Embedding (local sentence-transformers) ─────────────────────
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    # ── Retrieval ───────────────────────────────────────────────────
    chroma_path: Path = indexes_dir / "chroma"
    bm25_path: Path = indexes_dir / "bm25.pkl"
    top_k: int = 10
    rerank_top_k: int = 5

    # ── Agent ───────────────────────────────────────────────────────
    max_iterations: int = 6
    cost_per_query_budget: float = 0.05  # USD

    # ── Langfuse ────────────────────────────────────────────────────
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # ── API ─────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    secret_key: str = ""  # Set in .env file
    debug: bool = False

    # ── Database ────────────────────────────────────────────────────
    database_url: str = "sqlite:///./data.db"

    # ── Redis ───────────────────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_url: str = "redis://localhost:6379/0"

    # ── Rate Limiting ──────────────────────────────────────────────
    rate_limit_per_minute: int = 60
    daily_cost_limit: float = 10.0


settings = Settings()

# Create directories on import
for d in [settings.raw_dir, settings.processed_dir, settings.indexes_dir, settings.eval_dir]:
    d.mkdir(parents=True, exist_ok=True)
