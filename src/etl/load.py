"""Load the transformed frames into MySQL.

Steps:
  1. truncate fact + dims for an idempotent reload
  2. bulk-insert the dimensions
  3. read back the surrogate keys and remap natural keys on the fact rows
  4. bulk-insert the fact rows
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from src.config import pipeline_cfg
from src.db.connection import get_engine
from src.etl.transform import TransformedData

DIM_TABLES = ["dim_customer", "dim_product", "dim_store", "dim_date"]
FACT_TABLE = "fact_order_items"


def _truncate_all() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        conn.execute(text(f"TRUNCATE TABLE {FACT_TABLE}"))
        for t in DIM_TABLES:
            conn.execute(text(f"TRUNCATE TABLE {t}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


def _load_df(df: pd.DataFrame, table: str, chunksize: int) -> int:
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


def _load_dimensions(td: TransformedData) -> None:
    print("      loading dim_customer")
    _load_df(td.customers, "dim_customer", pipeline_cfg.batch_size)

    print("      loading dim_product")
    _load_df(td.products, "dim_product", pipeline_cfg.batch_size)

    print("      loading dim_store")
    _load_df(td.stores, "dim_store", pipeline_cfg.batch_size)

    print("      loading dim_date")
    _load_df(td.dim_date, "dim_date", pipeline_cfg.batch_size)


def _read_natural_to_surrogate(table: str, natural_col: str, surrogate_col: str) -> dict:
    sql = f"SELECT {natural_col}, {surrogate_col} FROM {table}"
    df = pd.read_sql(sql, get_engine())
    return dict(zip(df[natural_col], df[surrogate_col]))


def _build_fact_frame(td: TransformedData) -> pd.DataFrame:
    customer_map = _read_natural_to_surrogate("dim_customer", "customer_id", "customer_key")
    product_map  = _read_natural_to_surrogate("dim_product",  "product_id",  "product_key")
    store_map    = _read_natural_to_surrogate("dim_store",    "store_id",    "store_key")

    fact = td.orders.copy()
    fact["customer_key"] = fact["customer_id"].map(customer_map)
    fact["product_key"]  = fact["product_id"].map(product_map)
    fact["store_key"]    = fact["store_id"].map(store_map)

    # any unmapped row means transform() let an orphan through - bug
    bad = fact[fact[["customer_key", "product_key", "store_key"]].isna().any(axis=1)]
    if not bad.empty:
        raise RuntimeError(f"{len(bad)} fact rows failed surrogate-key lookup")

    fact_cols = [
        "order_id",
        "customer_key", "product_key", "date_key", "store_key",
        "quantity", "unit_price", "discount_amount", "total_amount",
        "order_status",
    ]
    return fact[fact_cols]


def load(td: TransformedData) -> dict:
    """Returns row counts loaded per table."""
    _truncate_all()
    _load_dimensions(td)

    print("      mapping natural keys to surrogate keys")
    fact_df = _build_fact_frame(td)

    print(f"      loading {len(fact_df):,} fact_order_items rows")
    n_fact = _load_df(fact_df, FACT_TABLE, pipeline_cfg.batch_size)

    return {
        "dim_customer": len(td.customers),
        "dim_product":  len(td.products),
        "dim_store":    len(td.stores),
        "dim_date":     len(td.dim_date),
        FACT_TABLE:     n_fact,
    }
