"""Cached vs uncached REST API response timing.

For each endpoint:
  1. clear the cache (POST /api/cache/clear)
  2. time the first request - cache miss (cold)
  3. time N follow-up requests - cache hits (warm)
  4. compute response time reduction

Server must be running at BASE_URL before running this.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import requests

BASE_URL = "http://localhost:5001"

ENDPOINTS = [
    "/api/metrics/revenue",
    "/api/metrics/revenue/monthly",
    "/api/categories/revenue",
    "/api/channels/revenue",
    "/api/products/top?limit=10",
    "/api/products/top?limit=50",
    "/api/customers/top?limit=10",
]


def clear_cache() -> None:
    requests.post(f"{BASE_URL}/api/cache/clear", timeout=10).raise_for_status()


def time_request(url: str) -> float:
    started = time.perf_counter()
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return time.perf_counter() - started


def benchmark(iterations: int) -> list[dict]:
    results = []
    print()
    print("=" * 92)
    print(f"  cached vs uncached api response  -  {iterations} warm hits per endpoint")
    print("=" * 92)
    print(f"  {'endpoint':<42} {'cold (ms)':>12} {'warm avg (ms)':>16} {'reduction':>12}")
    print(f"  {'-' * 42} {'-' * 12} {'-' * 16} {'-' * 12}")

    for ep in ENDPOINTS:
        clear_cache()
        url = BASE_URL + ep

        cold = time_request(url)

        warm = [time_request(url) for _ in range(iterations)]
        warm_mean = statistics.mean(warm)
        warm_stdev = statistics.stdev(warm) if len(warm) > 1 else 0
        reduction = (cold - warm_mean) / cold * 100 if cold else 0

        results.append({
            "endpoint":      ep,
            "cold_ms":       cold * 1000,
            "warm_mean_ms":  warm_mean * 1000,
            "warm_stdev_ms": warm_stdev * 1000,
            "reduction_pct": reduction,
        })

        print(f"  {ep:<42} {cold * 1000:>12.2f} {warm_mean * 1000:>16.2f} {reduction:>+11.1f}%")

    return results


def print_summary(results: list[dict]) -> None:
    print()
    print("=" * 92)
    print("  summary")
    print("=" * 92)
    avg_red = statistics.mean(r["reduction_pct"] for r in results)
    med_red = statistics.median(r["reduction_pct"] for r in results)
    print(f"  average response time reduction with cache: {avg_red:+.1f}%")
    print(f"  median  response time reduction with cache: {med_red:+.1f}%")
    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=10,
                        help="Warm hits per endpoint after the cold hit.")
    parser.add_argument("--out", type=str, default="benchmarks/api_results.json")
    args = parser.parse_args()

    try:
        requests.get(f"{BASE_URL}/api/health", timeout=5).raise_for_status()
    except requests.exceptions.RequestException as e:
        raise SystemExit(
            f"\ncan't reach api at {BASE_URL}\n"
            f"start it first: python -m src.api.app\n"
            f"error: {e}\n"
        )

    results = benchmark(args.iterations)
    print_summary(results)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))
    print(f"  results written to {out_path}")


if __name__ == "__main__":
    main()
