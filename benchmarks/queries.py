"""Paired analytical queries: star schema vs OLTP normalized.

Each pair returns identical aggregate results — same logical question,
just routed through different physical models. Used by star_vs_oltp.py.
"""
from __future__ import annotations

QUERIES: dict[str, dict[str, str]] = {

    "Q1: Top 5 categories by revenue": {
        "star": """
            SELECT p.category, ROUND(SUM(f.total_amount), 2) AS revenue
            FROM fact_order_items f
            JOIN dim_product p ON f.product_key = p.product_key
            GROUP BY p.category
            ORDER BY revenue DESC
            LIMIT 5
        """,
        "oltp": """
            SELECT c.name AS category, ROUND(SUM(ol.total_amount), 2) AS revenue
            FROM oltp_order_line ol
            JOIN oltp_product     p  ON ol.product_id     = p.product_id
            JOIN oltp_subcategory sc ON p.subcategory_id  = sc.subcategory_id
            JOIN oltp_category    c  ON sc.category_id    = c.category_id
            GROUP BY c.name
            ORDER BY revenue DESC
            LIMIT 5
        """,
    },

    "Q2: Monthly revenue trend": {
        "star": """
            SELECT d.year, d.month, ROUND(SUM(f.total_amount), 2) AS revenue
            FROM fact_order_items f
            JOIN dim_date d ON f.date_key = d.date_key
            GROUP BY d.year, d.month
            ORDER BY d.year, d.month
        """,
        "oltp": """
            SELECT YEAR(oh.order_date)  AS year,
                   MONTH(oh.order_date) AS month,
                   ROUND(SUM(ol.total_amount), 2) AS revenue
            FROM oltp_order_line  ol
            JOIN oltp_order_header oh ON ol.order_id = oh.order_id
            GROUP BY YEAR(oh.order_date), MONTH(oh.order_date)
            ORDER BY year, month
        """,
    },

    "Q3: Top 10 customers by lifetime value (with segment)": {
        "star": """
            SELECT c.customer_id, c.segment,
                   ROUND(SUM(f.total_amount), 2) AS lifetime_value
            FROM fact_order_items f
            JOIN dim_customer c ON f.customer_key = c.customer_key
            GROUP BY c.customer_id, c.segment
            ORDER BY lifetime_value DESC
            LIMIT 10
        """,
        "oltp": """
            SELECT c.customer_id, s.segment_name AS segment,
                   ROUND(SUM(ol.total_amount), 2) AS lifetime_value
            FROM oltp_order_line   ol
            JOIN oltp_order_header oh ON ol.order_id    = oh.order_id
            JOIN oltp_customer     c  ON oh.customer_id = c.customer_id
            JOIN oltp_segment      s  ON c.segment_id   = s.segment_id
            GROUP BY c.customer_id, s.segment_name
            ORDER BY lifetime_value DESC
            LIMIT 10
        """,
    },

    "Q4: Revenue by channel × region": {
        "star": """
            SELECT s.channel, s.region, ROUND(SUM(f.total_amount), 2) AS revenue
            FROM fact_order_items f
            JOIN dim_store s ON f.store_key = s.store_key
            GROUP BY s.channel, s.region
            ORDER BY revenue DESC
        """,
        "oltp": """
            SELECT s.channel, s.region, ROUND(SUM(ol.total_amount), 2) AS revenue
            FROM oltp_order_line   ol
            JOIN oltp_order_header oh ON ol.order_id = oh.order_id
            JOIN oltp_store        s  ON oh.store_id = s.store_id
            GROUP BY s.channel, s.region
            ORDER BY revenue DESC
        """,
    },

    "Q5: Revenue by category × month (cube)": {
        "star": """
            SELECT p.category, d.year, d.month,
                   ROUND(SUM(f.total_amount), 2) AS revenue
            FROM fact_order_items f
            JOIN dim_product p ON f.product_key = p.product_key
            JOIN dim_date    d ON f.date_key    = d.date_key
            GROUP BY p.category, d.year, d.month
            ORDER BY d.year, d.month, revenue DESC
        """,
        "oltp": """
            SELECT c.name AS category,
                   YEAR(oh.order_date)  AS year,
                   MONTH(oh.order_date) AS month,
                   ROUND(SUM(ol.total_amount), 2) AS revenue
            FROM oltp_order_line   ol
            JOIN oltp_order_header oh ON ol.order_id      = oh.order_id
            JOIN oltp_product      p  ON ol.product_id    = p.product_id
            JOIN oltp_subcategory  sc ON p.subcategory_id = sc.subcategory_id
            JOIN oltp_category     c  ON sc.category_id   = c.category_id
            GROUP BY c.name, YEAR(oh.order_date), MONTH(oh.order_date)
            ORDER BY year, month, revenue DESC
        """,
    },
}
