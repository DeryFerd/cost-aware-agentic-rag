#!/usr/bin/env python3
"""Load test script for the Cost-Aware Agentic RAG API.

No external dependencies required – uses only the standard library.

Usage:
    python scripts/load_test.py
    python scripts/load_test.py --users 20 --queries 10 --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SAMPLE_QUERIES = [
    "What was Microsoft revenue in 2024?",
    "Compare Amazon and Google revenue",
    "What are Tesla risk factors?",
    "How many employees does NVIDIA have?",
    "What is Apple profit margin?",
    "Compare Microsoft and Apple revenue growth",
    "What is Google revenue trend?",
    "What are Meta main products?",
    "How much does Amazon spend on R&D?",
    "What is NVIDIA gross margin?",
]


@dataclass
class RequestResult:
    status_code: int
    latency_ms: float
    error: str | None = None
    cost_usd: float = 0.0


@dataclass
class UserResult:
    user_id: int
    results: list[RequestResult] = field(default_factory=list)


def send_query(base_url: str, query: str, timeout: int = 120) -> RequestResult:
    """Send a single query to the /query endpoint and measure latency."""
    url = f"{base_url.rstrip('/')}/query"
    payload = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            latency_ms = (time.perf_counter() - t0) * 1000
            return RequestResult(
                status_code=resp.status,
                latency_ms=latency_ms,
                cost_usd=body.get("cost_usd", 0.0),
            )
    except urllib.error.HTTPError as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        return RequestResult(
            status_code=exc.code,
            latency_ms=latency_ms,
            error=str(exc),
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        return RequestResult(status_code=0, latency_ms=latency_ms, error=str(exc))


def simulate_user(
    user_id: int,
    base_url: str,
    queries_per_user: int,
    timeout: int,
) -> UserResult:
    """Simulate a single user sending *queries_per_user* requests."""
    import random

    result = UserResult(user_id=user_id)
    for _ in range(queries_per_user):
        query = random.choice(SAMPLE_QUERIES)
        req_result = send_query(base_url, query, timeout=timeout)
        result.results.append(req_result)
    return result


def percentile(data: list[float], p: float) -> float:
    """Calculate the p-th percentile of *data*."""
    if not data:
        return 0.0
    k = (len(data) - 1) * (p / 100)
    f = int(k)
    c = f + 1
    if c >= len(data):
        return data[-1]
    return data[f] + (k - f) * (data[c] - data[f])


def run_load_test(
    base_url: str,
    num_users: int,
    queries_per_user: int,
    timeout: int,
) -> dict[str, Any]:
    """Execute the load test and return aggregated metrics."""
    print(f"\nLoad test: {num_users} users x {queries_per_user} queries each")
    print(f"Target: {base_url}")
    print("-" * 50)

    total_requests = num_users * queries_per_user
    all_results: list[RequestResult] = []
    t_start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=num_users) as pool:
        futures = [
            pool.submit(simulate_user, i, base_url, queries_per_user, timeout)
            for i in range(num_users)
        ]
        for future in as_completed(futures):
            user_result = future.result()
            all_results.extend(user_result.results)
            sys.stdout.write(f"\r  Completed user {user_result.user_id + 1}/{num_users}")
            sys.stdout.flush()

    elapsed = time.perf_counter() - t_start
    print(f"\n\nCompleted in {elapsed:.1f}s")

    # Compute metrics
    latencies = sorted(r.latency_ms for r in all_results)
    errors = [r for r in all_results if r.status_code < 200 or r.status_code >= 300]
    costs = [r.cost_usd for r in all_results]

    metrics = {
        "config": {
            "base_url": base_url,
            "num_users": num_users,
            "queries_per_user": queries_per_user,
            "total_requests": total_requests,
        },
        "results": {
            "total_requests": total_requests,
            "successful": total_requests - len(errors),
            "errors": len(errors),
            "error_rate_pct": round(len(errors) / total_requests * 100, 2) if total_requests else 0,
            "elapsed_seconds": round(elapsed, 2),
            "requests_per_second": round(total_requests / elapsed, 2) if elapsed else 0,
        },
        "latency_ms": {
            "min": round(latencies[0], 2) if latencies else 0,
            "max": round(latencies[-1], 2) if latencies else 0,
            "mean": round(statistics.mean(latencies), 2) if latencies else 0,
            "median": round(statistics.median(latencies), 2) if latencies else 0,
            "p50": round(percentile(latencies, 50), 2),
            "p95": round(percentile(latencies, 95), 2),
            "p99": round(percentile(latencies, 99), 2),
            "stdev": round(statistics.stdev(latencies), 2) if len(latencies) > 1 else 0,
        },
        "cost": {
            "total_usd": round(sum(costs), 6),
            "mean_per_request_usd": round(statistics.mean(costs), 6) if costs else 0,
        },
        "errors_sample": [
            {"status_code": e.status_code, "error": e.error, "latency_ms": round(e.latency_ms, 2)}
            for e in errors[:10]
        ],
    }

    return metrics


def print_summary(metrics: dict[str, Any]) -> None:
    """Pretty-print the load test summary."""
    r = metrics["results"]
    l = metrics["latency_ms"]
    c = metrics["cost"]

    print("\n" + "=" * 55)
    print("  LOAD TEST RESULTS")
    print("=" * 55)
    print(f"  Total requests:   {r['total_requests']}")
    print(f"  Successful:       {r['successful']}")
    print(f"  Errors:           {r['errors']} ({r['error_rate_pct']}%)")
    print(f"  Elapsed:          {r['elapsed_seconds']}s")
    print(f"  Requests/sec:     {r['requests_per_second']}")
    print("-" * 55)
    print(f"  Latency min:      {l['min']}ms")
    print(f"  Latency max:      {l['max']}ms")
    print(f"  Latency mean:     {l['mean']}ms")
    print(f"  Latency median:   {l['median']}ms")
    print(f"  Latency p50:      {l['p50']}ms")
    print(f"  Latency p95:      {l['p95']}ms")
    print(f"  Latency p99:      {l['p99']}ms")
    print(f"  Latency stdev:    {l['stdev']}ms")
    print("-" * 55)
    print(f"  Total cost:       ${c['total_usd']}")
    print(f"  Mean cost/req:    ${c['mean_per_request_usd']}")
    print("=" * 55)

    if metrics["errors_sample"]:
        print("\n  Error samples:")
        for err in metrics["errors_sample"][:5]:
            print(f"    [{err['status_code']}] {err['error']} ({err['latency_ms']}ms)")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load test the Cost-Aware Agentic RAG API")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--users", type=int, default=10, help="Number of concurrent users")
    parser.add_argument("--queries", type=int, default=5, help="Queries per user")
    parser.add_argument("--timeout", type=int, default=120, help="Request timeout in seconds")
    parser.add_argument("--output", default="data/metrics/load_test.json", help="Output file path")
    args = parser.parse_args()

    metrics = run_load_test(args.base_url, args.users, args.queries, args.timeout)
    print_summary(metrics)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metrics, indent=2))
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()
