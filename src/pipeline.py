"""ETL pipeline runner."""
from __future__ import annotations

import time

from src.etl.extract import extract
from src.etl.load import load
from src.etl.transform import transform


def run() -> None:
    started = time.perf_counter()

    print("[1/3] extract")
    raw = extract()
    print(
        f"      customers={len(raw.customers):,} "
        f"products={len(raw.products):,} "
        f"stores={len(raw.stores):,} "
        f"orders={len(raw.orders):,}"
    )

    print("[2/3] transform")
    td = transform(raw)

    print("[3/3] load")
    counts = load(td)

    elapsed = time.perf_counter() - started
    total_rows = sum(counts.values())
    print("\ndone")
    for table, n in counts.items():
        print(f"    {table:<22} {n:>10,} rows")
    print(f"  total rows: {total_rows:,}")
    print(f"  elapsed:    {elapsed:.2f}s")
    if elapsed > 0:
        print(f"  throughput: {total_rows / elapsed:,.0f} rows/sec")


if __name__ == "__main__":
    run()
