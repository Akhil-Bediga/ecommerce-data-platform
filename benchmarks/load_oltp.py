"""Load the same raw CSVs into a 10-table 3NF schema for benchmarking.

Same underlying data as the star schema, but normalized the way an upstream
OLTP system would store it.
"""
from __future__ import annotations

import time

import pandas as pd
from sqlalchemy import text

from src.config import pipeline_cfg
from src.db.connection import get_engine

SEGMENT_MAP = {"NEW": 1, "REGULAR": 2, "VIP": 3}

OLTP_TABLES_REVERSE = [
    "oltp_order_line", "oltp_order_header",
    "oltp_product", "oltp_subcategory", "oltp_category", "oltp_brand",
    "oltp_address", "oltp_customer", "oltp_segment",
    "oltp_store",
]


def truncate_all() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for t in OLTP_TABLES_REVERSE:
            conn.execute(text(f"TRUNCATE TABLE {t}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


def _bulk(df: pd.DataFrame, table: str, chunksize: int = 5000) -> int:
    if df.empty:
        return 0
    df.to_sql(
        table,
        get_engine(),
        if_exists="append",
        index=False,
        chunksize=chunksize,
        method="multi",
    )
    return len(df)


def load() -> dict:
    raw = pipeline_cfg.data_dir / "raw"
    customers = pd.read_csv(raw / "customers.csv")
    products  = pd.read_csv(raw / "products.csv")
    stores    = pd.read_csv(raw / "stores.csv")
    orders    = pd.read_csv(raw / "orders.csv")

    engine = get_engine()
    counts: dict = {}

    # 1. Segments
    print("      oltp_segment")
    seg_df = pd.DataFrame(
        [{"segment_id": v, "segment_name": k} for k, v in SEGMENT_MAP.items()]
    )
    counts["oltp_segment"] = _bulk(seg_df, "oltp_segment")

    # 2. Customers
    print("      oltp_customer")
    cust = customers.drop_duplicates(subset=["customer_id"]).copy()
    cust["segment_id"] = cust["segment"].map(SEGMENT_MAP).fillna(1).astype(int)
    counts["oltp_customer"] = _bulk(
        cust[["customer_id", "first_name", "last_name", "email", "signup_date", "segment_id"]],
        "oltp_customer",
    )

    # 3. Addresses (one per customer; real OLTP would allow multiple)
    print("      oltp_address")
    addr = customers[["customer_id", "country", "city"]].drop_duplicates(subset=["customer_id"])
    counts["oltp_address"] = _bulk(addr, "oltp_address")

    # 4. Categories
    print("      oltp_category")
    cat_df = pd.DataFrame({"name": sorted(products["category"].dropna().unique())})
    counts["oltp_category"] = _bulk(cat_df, "oltp_category")
    cat_map = dict(
        pd.read_sql("SELECT name, category_id FROM oltp_category", engine).itertuples(index=False, name=None)
    )

    # 5. Subcategories (composite uniqueness on category_id + name)
    print("      oltp_subcategory")
    subcat = (
        products[["category", "subcategory"]]
        .dropna()
        .drop_duplicates()
        .rename(columns={"subcategory": "name"})
    )
    subcat["category_id"] = subcat["category"].map(cat_map)
    counts["oltp_subcategory"] = _bulk(
        subcat[["category_id", "name"]], "oltp_subcategory"
    )
    subcat_lookup_df = pd.read_sql(
        "SELECT s.subcategory_id, c.name AS cat, s.name AS sub "
        "FROM oltp_subcategory s JOIN oltp_category c ON s.category_id = c.category_id",
        engine,
    )
    subcat_map = {(r.cat, r.sub): r.subcategory_id for r in subcat_lookup_df.itertuples()}

    # 6. Brands
    print("      oltp_brand")
    brand_df = pd.DataFrame({"name": sorted(products["brand"].dropna().unique())})
    counts["oltp_brand"] = _bulk(brand_df, "oltp_brand")
    brand_map = dict(
        pd.read_sql("SELECT name, brand_id FROM oltp_brand", engine).itertuples(index=False, name=None)
    )

    # 7. Products
    print("      oltp_product")
    prod = products.drop_duplicates(subset=["product_id"]).copy()
    prod["brand_id"] = prod["brand"].map(brand_map)
    prod["subcategory_id"] = [
        subcat_map.get((c, s)) for c, s in zip(prod["category"], prod["subcategory"])
    ]
    prod = prod.dropna(subset=["brand_id", "subcategory_id"])
    prod["brand_id"] = prod["brand_id"].astype(int)
    prod["subcategory_id"] = prod["subcategory_id"].astype(int)
    counts["oltp_product"] = _bulk(
        prod[["product_id", "name", "brand_id", "subcategory_id", "base_price"]],
        "oltp_product",
    )

    # 8. Stores
    print("      oltp_store")
    counts["oltp_store"] = _bulk(stores.drop_duplicates(subset=["store_id"]), "oltp_store")

    # 9. Order headers - one row per unique order_id, take attrs from first line
    print("      oltp_order_header")
    headers = (
        orders.drop_duplicates(subset=["order_id"], keep="first")[
            ["order_id", "customer_id", "store_id", "order_date", "order_status"]
        ]
    )
    counts["oltp_order_header"] = _bulk(headers, "oltp_order_header", chunksize=5000)

    # 10. Order lines
    print("      oltp_order_line")
    lines = orders[["order_id", "product_id", "quantity", "unit_price", "discount_amount", "total_amount"]]
    counts["oltp_order_line"] = _bulk(lines, "oltp_order_line", chunksize=5000)

    return counts


def main() -> None:
    print("truncating OLTP tables")
    truncate_all()
    print("loading OLTP tables from raw CSVs")
    started = time.perf_counter()
    counts = load()
    elapsed = time.perf_counter() - started
    print("\nOLTP load done")
    for t, n in counts.items():
        print(f"    {t:<22} {n:>10,} rows")
    print(f"  elapsed: {elapsed:.2f}s")


if __name__ == "__main__":
    main()
