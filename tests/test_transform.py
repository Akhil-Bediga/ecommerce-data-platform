"""Unit tests for the transform layer."""
from datetime import date

import pandas as pd
import pytest

from src.etl.extract import RawData
from src.etl.transform import (
    _build_dim_date,
    _clean_customers,
    _clean_orders,
    _clean_products,
    _clean_stores,
    transform,
)


def test_clean_customers_dedupes_by_id():
    df = pd.DataFrame([
        {"customer_id": "c1", "first_name": "A", "last_name": "B",
         "email": "a@b.com", "country": "US", "city": "NY",
         "signup_date": "2024-01-01", "segment": "VIP"},
        {"customer_id": "c1", "first_name": "A", "last_name": "B",
         "email": "a@b.com", "country": "US", "city": "NY",
         "signup_date": "2024-01-01", "segment": "VIP"},
        {"customer_id": "c2", "first_name": "X", "last_name": "Y",
         "email": "X@Y.com", "country": "US", "city": "LA",
         "signup_date": "2024-01-02", "segment": "REGULAR"},
    ])
    out = _clean_customers(df)
    assert len(out) == 2
    assert set(out["customer_id"]) == {"c1", "c2"}


def test_clean_customers_normalizes_email_and_segment():
    df = pd.DataFrame([{
        "customer_id": "c1", "first_name": "A", "last_name": "B",
        "email": "  Foo@BAR.com  ", "country": None, "city": None,
        "signup_date": "2024-01-01", "segment": "weird_value",
    }])
    out = _clean_customers(df)
    assert out.iloc[0]["email"] == "foo@bar.com"
    assert out.iloc[0]["segment"] == "NEW"
    assert out.iloc[0]["country"] == "Unknown"


def test_clean_orders_drops_orphans():
    orders = pd.DataFrame([
        {"order_id": "o1", "customer_id": "c1", "product_id": "p1",
         "store_id": "s1", "order_date": "2024-01-01", "quantity": 1,
         "unit_price": 10, "discount_amount": 0, "total_amount": 10,
         "order_status": "PLACED"},
        {"order_id": "o2", "customer_id": "GHOST", "product_id": "p1",
         "store_id": "s1", "order_date": "2024-01-01", "quantity": 1,
         "unit_price": 10, "discount_amount": 0, "total_amount": 10,
         "order_status": "PLACED"},
    ])
    out = _clean_orders(orders, {"c1"}, {"p1"}, {"s1"})
    assert len(out) == 1
    assert out.iloc[0]["order_id"] == "o1"


def test_clean_orders_recomputes_total_amount():
    """Don't trust the upstream total_amount column - recompute from qty * price - discount."""
    orders = pd.DataFrame([{
        "order_id": "o1", "customer_id": "c1", "product_id": "p1",
        "store_id": "s1", "order_date": "2024-01-01",
        "quantity": 3, "unit_price": 10, "discount_amount": 5,
        "total_amount": 999,  # bogus value, should get recomputed
        "order_status": "DELIVERED",
    }])
    out = _clean_orders(orders, {"c1"}, {"p1"}, {"s1"})
    assert out.iloc[0]["total_amount"] == 25.0  # 3*10 - 5 = 25


def test_clean_orders_drops_zero_quantity():
    orders = pd.DataFrame([
        {"order_id": "o1", "customer_id": "c1", "product_id": "p1",
         "store_id": "s1", "order_date": "2024-01-01", "quantity": 0,
         "unit_price": 10, "discount_amount": 0, "total_amount": 0,
         "order_status": "PLACED"},
    ])
    out = _clean_orders(orders, {"c1"}, {"p1"}, {"s1"})
    assert len(out) == 0


def test_clean_orders_builds_date_key():
    orders = pd.DataFrame([{
        "order_id": "o1", "customer_id": "c1", "product_id": "p1",
        "store_id": "s1", "order_date": "2024-03-15", "quantity": 1,
        "unit_price": 10, "discount_amount": 0, "total_amount": 10,
        "order_status": "PLACED",
    }])
    out = _clean_orders(orders, {"c1"}, {"p1"}, {"s1"})
    assert out.iloc[0]["date_key"] == 20240315


def test_clean_orders_rejects_bad_status():
    orders = pd.DataFrame([{
        "order_id": "o1", "customer_id": "c1", "product_id": "p1",
        "store_id": "s1", "order_date": "2024-01-01", "quantity": 1,
        "unit_price": 10, "discount_amount": 0, "total_amount": 10,
        "order_status": "FAKE_STATUS",
    }])
    out = _clean_orders(orders, {"c1"}, {"p1"}, {"s1"})
    assert out.iloc[0]["order_status"] == "PLACED"


def test_dim_date_covers_order_range_plus_buffer():
    orders = pd.DataFrame({
        "order_date": [date(2024, 1, 1), date(2024, 6, 1)],
    })
    dim = _build_dim_date(orders)
    assert dim["full_date"].min() == date(2024, 1, 1)
    # min + 1 year buffer
    assert dim["full_date"].max() >= date(2025, 5, 31)
    assert (dim["is_weekend"].isin([0, 1])).all()


def test_clean_products_fills_nulls():
    df = pd.DataFrame([{
        "product_id": "p1", "name": None, "category": None,
        "subcategory": None, "brand": None, "base_price": None,
    }])
    out = _clean_products(df)
    assert out.iloc[0]["name"] == "Unknown"
    assert out.iloc[0]["category"] == "Other"
    assert out.iloc[0]["brand"] == "Generic"
    assert out.iloc[0]["base_price"] == 0


def test_clean_stores_normalizes_channel():
    df = pd.DataFrame([
        {"store_id": "s1", "name": "S1", "region": "NA", "country": "US", "channel": "online"},
        {"store_id": "s2", "name": "S2", "region": "EU", "country": "DE", "channel": "BOGUS"},
    ])
    out = _clean_stores(df)
    assert out.iloc[0]["channel"] == "ONLINE"
    assert out.iloc[1]["channel"] == "ONLINE"  # bad value defaults to ONLINE


def test_full_transform_end_to_end():
    """Smoke test the public transform() with tiny synthetic input."""
    raw = RawData(
        customers=pd.DataFrame([{
            "customer_id": "c1", "first_name": "A", "last_name": "B",
            "email": "a@b.com", "country": "US", "city": "NY",
            "signup_date": "2024-01-01", "segment": "VIP",
        }]),
        products=pd.DataFrame([{
            "product_id": "p1", "name": "Thing", "category": "Apparel",
            "subcategory": "Shirts", "brand": "Acme", "base_price": 25.0,
        }]),
        stores=pd.DataFrame([{
            "store_id": "s1", "name": "Main", "region": "NA",
            "country": "US", "channel": "ONLINE",
        }]),
        orders=pd.DataFrame([{
            "order_id": "o1", "customer_id": "c1", "product_id": "p1",
            "store_id": "s1", "order_date": "2024-05-01",
            "quantity": 2, "unit_price": 25, "discount_amount": 0,
            "total_amount": 50, "order_status": "DELIVERED",
        }]),
    )
    out = transform(raw)
    assert len(out.customers) == 1
    assert len(out.products) == 1
    assert len(out.stores) == 1
    assert len(out.orders) == 1
    assert len(out.dim_date) > 0
    assert out.orders.iloc[0]["date_key"] == 20240501
