"""Clean and reshape the raw data into dim/fact-shaped frames.

The load step assigns surrogate keys, so we leave those off here and just
pass the natural keys through.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from src.etl.extract import RawData


@dataclass
class TransformedData:
    customers: pd.DataFrame
    products: pd.DataFrame
    stores: pd.DataFrame
    dim_date: pd.DataFrame
    orders: pd.DataFrame   # fact-shaped, still with natural keys


def _clean_customers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates(subset=["customer_id"]).copy()
    df["email"] = df["email"].str.strip().str.lower()
    df["country"] = df["country"].fillna("Unknown").str.slice(0, 60)
    df["city"] = df["city"].fillna("Unknown").str.slice(0, 80)
    df["signup_date"] = pd.to_datetime(df["signup_date"]).dt.date
    df["segment"] = df["segment"].fillna("NEW").str.upper()
    df.loc[~df["segment"].isin(["NEW", "REGULAR", "VIP"]), "segment"] = "NEW"
    return df


def _clean_products(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates(subset=["product_id"]).copy()
    df["name"] = df["name"].fillna("Unknown").str.slice(0, 160)
    df["category"] = df["category"].fillna("Other")
    df["subcategory"] = df["subcategory"].fillna("Other")
    df["brand"] = df["brand"].fillna("Generic")
    df["base_price"] = pd.to_numeric(df["base_price"], errors="coerce").fillna(0).round(2)
    return df


def _clean_stores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates(subset=["store_id"]).copy()
    df["channel"] = df["channel"].str.upper()
    df.loc[~df["channel"].isin(["ONLINE", "MOBILE", "RETAIL"]), "channel"] = "ONLINE"
    return df


def _clean_orders(
    df: pd.DataFrame,
    valid_customer_ids: set,
    valid_product_ids: set,
    valid_store_ids: set,
) -> pd.DataFrame:
    df = df.copy()

    # drop rows with FKs that don't exist in the dimensions
    before = len(df)
    df = df[df["customer_id"].isin(valid_customer_ids)]
    df = df[df["product_id"].isin(valid_product_ids)]
    df = df[df["store_id"].isin(valid_store_ids)]
    dropped = before - len(df)
    if dropped:
        print(f"      dropped {dropped:,} orphan order rows")

    df["order_date"] = pd.to_datetime(df["order_date"]).dt.date
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce").fillna(0).round(2)
    df["discount_amount"] = pd.to_numeric(df["discount_amount"], errors="coerce").fillna(0).round(2)

    # recompute total to avoid trusting upstream data
    df["total_amount"] = (
        (df["unit_price"] * df["quantity"]) - df["discount_amount"]
    ).clip(lower=0).round(2)

    df["date_key"] = pd.to_datetime(df["order_date"]).dt.strftime("%Y%m%d").astype(int)

    df["order_status"] = df["order_status"].fillna("PLACED").str.upper()
    valid_statuses = {"PLACED", "SHIPPED", "DELIVERED", "RETURNED", "CANCELLED"}
    df.loc[~df["order_status"].isin(valid_statuses), "order_status"] = "PLACED"

    df = df[df["quantity"] > 0]
    return df


def _build_dim_date(orders: pd.DataFrame) -> pd.DataFrame:
    """Build the date dim covering all order dates plus a year buffer."""
    if orders.empty:
        return pd.DataFrame()
    min_d = pd.to_datetime(orders["order_date"]).min().date()
    max_d = pd.to_datetime(orders["order_date"]).max().date() + timedelta(days=365)
    dates = pd.date_range(min_d, max_d, freq="D")

    return pd.DataFrame({
        "date_key":    dates.strftime("%Y%m%d").astype(int),
        "full_date":   dates.date,
        "day":         dates.day,
        "month":       dates.month,
        "quarter":     dates.quarter,
        "year":        dates.year,
        "day_of_week": dates.dayofweek + 1,           # 1=Mon..7=Sun
        "is_weekend":  (dates.dayofweek >= 5).astype(int),
    })


def transform(raw: RawData) -> TransformedData:
    print("      cleaning dimensions")
    customers = _clean_customers(raw.customers)
    products = _clean_products(raw.products)
    stores = _clean_stores(raw.stores)

    print("      cleaning orders")
    orders = _clean_orders(
        raw.orders,
        valid_customer_ids=set(customers["customer_id"]),
        valid_product_ids=set(products["product_id"]),
        valid_store_ids=set(stores["store_id"]),
    )

    print("      building dim_date")
    dim_date = _build_dim_date(orders)

    return TransformedData(
        customers=customers,
        products=products,
        stores=stores,
        dim_date=dim_date,
        orders=orders,
    )
