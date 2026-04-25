"""REST endpoints over the star schema, with a 60-second TTL cache."""
from __future__ import annotations

from typing import Any

from cachetools import TTLCache
from flask import Blueprint, jsonify, request
from sqlalchemy import text

from src.db.connection import get_engine

api_bp = Blueprint("api", __name__, url_prefix="/api")

_cache: TTLCache = TTLCache(maxsize=512, ttl=60)


def _query(sql: str, params: dict | None = None) -> list[dict[str, Any]]:
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql), params or {}).fetchall()
    return [dict(r._mapping) for r in rows]


def _cached(key: tuple, fn) -> Any:
    if key in _cache:
        return _cache[key]
    value = fn()
    _cache[key] = value
    return value


@api_bp.get("/health")
def health():
    return {"status": "ok", "cache_size": len(_cache)}


@api_bp.post("/cache/clear")
def clear_cache():
    n = len(_cache)
    _cache.clear()
    return {"cleared": n}


@api_bp.get("/metrics/revenue")
def revenue():
    f = request.args.get("from")
    t = request.args.get("to")
    key = ("revenue", f, t)

    def fn():
        where, params = [], {}
        if f:
            where.append("d.full_date >= :from"); params["from"] = f
        if t:
            where.append("d.full_date <= :to");   params["to"]   = t
        clause = "WHERE " + " AND ".join(where) if where else ""
        sql = f"""
            SELECT ROUND(SUM(f.total_amount), 2) AS revenue,
                   COUNT(*)                       AS line_items
            FROM fact_order_items f
            JOIN dim_date d ON f.date_key = d.date_key
            {clause}
        """
        return _query(sql, params)

    return jsonify(_cached(key, fn))


@api_bp.get("/metrics/revenue/monthly")
def revenue_monthly():
    def fn():
        return _query("""
            SELECT d.year, d.month, ROUND(SUM(f.total_amount), 2) AS revenue
            FROM fact_order_items f
            JOIN dim_date d ON f.date_key = d.date_key
            GROUP BY d.year, d.month
            ORDER BY d.year, d.month
        """)
    return jsonify(_cached(("revenue_monthly",), fn))


@api_bp.get("/categories/revenue")
def categories_revenue():
    def fn():
        return _query("""
            SELECT p.category, ROUND(SUM(f.total_amount), 2) AS revenue
            FROM fact_order_items f
            JOIN dim_product p ON f.product_key = p.product_key
            GROUP BY p.category
            ORDER BY revenue DESC
        """)
    return jsonify(_cached(("categories_revenue",), fn))


@api_bp.get("/products/top")
def top_products():
    limit = min(int(request.args.get("limit", 10)), 100)

    def fn():
        return _query("""
            SELECT p.product_id, p.name, p.category, p.brand,
                   SUM(f.quantity)                   AS units_sold,
                   ROUND(SUM(f.total_amount), 2)     AS revenue
            FROM fact_order_items f
            JOIN dim_product p ON f.product_key = p.product_key
            GROUP BY p.product_id, p.name, p.category, p.brand
            ORDER BY revenue DESC
            LIMIT :limit
        """, {"limit": limit})

    return jsonify(_cached(("top_products", limit), fn))


@api_bp.get("/customers/top")
def top_customers():
    limit = min(int(request.args.get("limit", 10)), 100)

    def fn():
        return _query("""
            SELECT c.customer_id, c.first_name, c.last_name, c.segment,
                   COUNT(DISTINCT f.order_id)      AS orders,
                   ROUND(SUM(f.total_amount), 2)   AS lifetime_value
            FROM fact_order_items f
            JOIN dim_customer c ON f.customer_key = c.customer_key
            GROUP BY c.customer_id, c.first_name, c.last_name, c.segment
            ORDER BY lifetime_value DESC
            LIMIT :limit
        """, {"limit": limit})

    return jsonify(_cached(("top_customers", limit), fn))


@api_bp.get("/customers/<customer_id>/orders")
def customer_orders(customer_id: str):
    def fn():
        return _query("""
            SELECT f.order_id, d.full_date AS order_date,
                   p.name AS product, p.category,
                   f.quantity, f.unit_price, f.total_amount, f.order_status
            FROM fact_order_items f
            JOIN dim_customer c ON f.customer_key = c.customer_key
            JOIN dim_product  p ON f.product_key  = p.product_key
            JOIN dim_date     d ON f.date_key     = d.date_key
            WHERE c.customer_id = :customer_id
            ORDER BY d.full_date DESC
            LIMIT 100
        """, {"customer_id": customer_id})

    return jsonify(_cached(("customer_orders", customer_id), fn))


@api_bp.get("/channels/revenue")
def channels_revenue():
    def fn():
        return _query("""
            SELECT s.channel, s.region,
                   ROUND(SUM(f.total_amount), 2) AS revenue,
                   COUNT(*)                      AS orders
            FROM fact_order_items f
            JOIN dim_store s ON f.store_key = s.store_key
            GROUP BY s.channel, s.region
            ORDER BY revenue DESC
        """)
    return jsonify(_cached(("channels_revenue",), fn))
