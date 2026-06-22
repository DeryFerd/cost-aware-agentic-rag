"""Validate environment configuration before deployment."""

import os
import sys
from pathlib import Path


def check(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return condition


def main() -> int:
    print("=== Environment Validation ===\n")

    all_pass = True

    # ── Required env vars ────────────────────────────────────────────
    print("Required environment variables:")
    required = {
        "OLLAMA_HOST": "Ollama server URL",
        "OLLAMA_API_KEY": "Ollama Cloud API key",
    }
    for var, desc in required.items():
        val = os.environ.get(var, "")
        all_pass &= check(var, bool(val.strip()), desc)

    print("\nDocker / admin panel variables:")
    docker_vars = {
        "ADMIN_USERNAME": "Admin panel username",
        "ADMIN_PASSWORD": "Admin panel password",
        "SECRET_KEY": "Session signing key (required for Docker)",
    }
    for var, desc in docker_vars.items():
        val = os.environ.get(var, "")
        # These are required for Docker but not for local dev with uvicorn
        # Only warn here; the docker-compose file enforces SECRET_KEY
        check(var, bool(val.strip()), f"{desc} — {'set' if val.strip() else 'NOT SET (needed for Docker)'}")

    print("\nOptional environment variables:")
    optional = {
        "REDIS_URL": "Redis caching",
        "LANGFUSE_PUBLIC_KEY": "Langfuse tracing",
        "LANGFUSE_SECRET_KEY": "Langfuse tracing",
        "LANGFUSE_HOST": "Langfuse instance",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "OpenTelemetry collector",
    }
    for var, desc in optional.items():
        val = os.environ.get(var, "")
        check(var, True, f"{desc} — {'set' if val.strip() else 'not set (optional)'}")

    # ── Ollama connectivity ──────────────────────────────────────────
    print("\nOllama server connectivity:")
    ollama_host = os.environ.get("OLLAMA_HOST", "https://ollama.com")
    try:
        import urllib.request
        req = urllib.request.Request(ollama_host, method="HEAD")
        urllib.request.urlopen(req, timeout=5)
        all_pass &= check("Ollama reachable", True, ollama_host)
    except Exception as e:
        all_pass &= check("Ollama reachable", False, f"{ollama_host} — {e}")

    # ── Redis connectivity ───────────────────────────────────────────
    print("\nRedis connectivity:")
    redis_url = os.environ.get("REDIS_URL", "")
    if redis_url.strip():
        try:
            import socket
            from urllib.parse import urlparse
            parsed = urlparse(redis_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 6379
            sock = socket.create_connection((host, port), timeout=5)
            sock.close()
            all_pass &= check("Redis reachable", True, redis_url)
        except Exception as e:
            all_pass &= check("Redis reachable", False, f"{redis_url} — {e}")
    else:
        check("Redis reachable", True, "REDIS_URL not set (skipped)")

    # ── Data directories ─────────────────────────────────────────────
    print("\nData directories:")
    project_root = Path(__file__).resolve().parent.parent
    dirs = {
        "data/raw": project_root / "data" / "raw",
        "data/processed": project_root / "data" / "processed",
        "data/indexes": project_root / "data" / "indexes",
    }
    for label, path in dirs.items():
        exists = path.is_dir()
        all_pass &= check(label, exists, str(path) if exists else "does not exist (run ingest.py)")

    # ── Summary ──────────────────────────────────────────────────────
    print()
    if all_pass:
        print("All checks passed.")
    else:
        print("Some checks failed. Fix the issues above before deploying.")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
