"""Star schema vs OLTP normalized - timing benchmark.

For each query pair:
  - run N iterations on each schema, drop the first as warmup
  - average the rest
  - check that both queries returned the same row count
  - speedup = (oltp_avg - star_avg) / oltp_avg * 100
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from sqlalchemy import text

from src.db.connection import get_engine
from benchmarks.queries import QUERIES


def time_query(conn, sql: str, iterations: int) -> tuple[list[float], int]:
    timings: list[float] = []
    rowcount = 0
    for _ in range(iterations):
        started = time.perf_counter()
        result = conn.execute(text(sql))
        rows = result.fetchall()
        timings.append(time.perf_counter() - started)
        rowcount = len(rows)
    return timings[1:], rowcount   # drop warm-up


def fmt_ms(seconds: float) -> str:
    return f"{seconds * 1000:>8.2f} ms"


def run(iterations: int) -> list[dict]:
    engine = get_engine()
    results = []

    print()
    print("=" * 88)
    print(f"  star schema vs oltp normalized  -  {iterations} iterations per query (1 warmup dropped)")
    print("=" * 88)

    with engine.connect() as conn:
        # warm both buffer pools
        conn.execute(text("SELECT COUNT(*) FROM fact_order_items")).fetchone()
        conn.execute(text("SELECT COUNT(*) FROM oltp_order_line")).fetchone()

        for name, queries in QUERIES.items():
            star_t, star_rows = time_query(conn, queries["star"], iterations)
            oltp_t, oltp_rows = time_query(conn, queries["oltp"], iterations)

            star_mean = statistics.mean(star_t)
            oltp_mean = statistics.mean(oltp_t)
            star_stdev = statistics.stdev(star_t) if len(star_t) > 1 else 0
            oltp_stdev = statistics.stdev(oltp_t) if len(oltp_t) > 1 else 0
            speedup = (oltp_mean - star_mean) / oltp_mean * 100 if oltp_mean else 0.0

            results.append({
                "query": name,
                "star_ms":     star_mean * 1000,
                "star_stdev":  star_stdev * 1000,
                "oltp_ms":     oltp_mean * 1000,
                "oltp_stdev":  oltp_stdev * 1000,
                "speedup_pct": speedup,
                "star_rows":   star_rows,
                "oltp_rows":   oltp_rows,
                "rows_match":  star_rows == oltp_rows,
            })

            match_marker = "ok" if star_rows == oltp_rows else "MISMATCH"
            print(f"\n  {name}")
            print(f"     star: {fmt_ms(star_mean)} (+/-{star_stdev*1000:5.2f})  "
                  f"oltp: {fmt_ms(oltp_mean)} (+/-{oltp_stdev*1000:5.2f})  "
                  f"speedup: {speedup:+6.1f}%  rows: {star_rows} {match_marker} {oltp_rows}")

    return results


def print_summary(results: list[dict]) -> None:
    print()
    print("=" * 88)
    print("  summary")
    print("=" * 88)
    print(f"  {'query':<48} {'star (ms)':>12} {'oltp (ms)':>12} {'speedup':>10}")
    print(f"  {'-'*48} {'-'*12} {'-'*12} {'-'*10}")
    for r in results:
        print(f"  {r['query']:<48} {r['star_ms']:>12.2f} {r['oltp_ms']:>12.2f} {r['speedup_pct']:>+9.1f}%")

    avg_speedup = statistics.mean(r["speedup_pct"] for r in results)
    median_speedup = statistics.median(r["speedup_pct"] for r in results)
    print(f"  {'-'*48} {'-'*12} {'-'*12} {'-'*10}")
    print(f"  average star schema speedup: {avg_speedup:+.1f}%")
    print(f"  median  star schema speedup: {median_speedup:+.1f}%")
    print()

    if all(r["rows_match"] for r in results):
        print("  all queries returned matching row counts")
    else:
        print("  WARNING: row count mismatch on one or more queries")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=6,
                        help="Total iterations per query (1st discarded as warm-up).")
    parser.add_argument("--out", type=str, default="benchmarks/results.json",
                        help="Where to write the JSON results.")
    args = parser.parse_args()

    results = run(args.iterations)
    print_summary(results)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\n  results written to {out_path}")


if __name__ == "__main__":
    main()
