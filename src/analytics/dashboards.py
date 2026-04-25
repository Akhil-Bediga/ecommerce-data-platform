"""Generate matplotlib dashboards from the star schema.

Output PNGs land in docs/dashboards/ - used by the README and for demos.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.config import PROJECT_ROOT
from src.db.connection import get_engine

OUT_DIR = PROJECT_ROOT / "docs" / "dashboards"

plt.rcParams.update({
    "figure.facecolor":  "white",
    "axes.facecolor":    "white",
    "axes.grid":         True,
    "grid.alpha":        0.25,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "font.size":         11,
})


def _save(fig: plt.Figure, name: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_monthly_revenue() -> Path:
    df = pd.read_sql("""
        SELECT d.year, d.month, SUM(f.total_amount) AS revenue
        FROM fact_order_items f
        JOIN dim_date d ON f.date_key = d.date_key
        GROUP BY d.year, d.month
        ORDER BY d.year, d.month
    """, get_engine())
    df["period"] = df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2)

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["period"], df["revenue"] / 1_000_000, marker="o", linewidth=2.2, color="#2E86AB")
    ax.fill_between(df["period"], df["revenue"] / 1_000_000, alpha=0.15, color="#2E86AB")
    ax.set_title("Monthly Revenue Trend", fontsize=14, fontweight="bold")
    ax.set_xlabel("Month")
    ax.set_ylabel("Revenue ($M)")
    plt.xticks(rotation=45)
    return _save(fig, "monthly_revenue.png")


def chart_categories() -> Path:
    df = pd.read_sql("""
        SELECT p.category, SUM(f.total_amount) AS revenue
        FROM fact_order_items f
        JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.category
        ORDER BY revenue ASC
    """, get_engine())

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(df["category"], df["revenue"] / 1_000_000, color="#A23B72")
    ax.set_title("Revenue by Product Category", fontsize=14, fontweight="bold")
    ax.set_xlabel("Revenue ($M)")
    for bar in bars:
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"${bar.get_width():.1f}M", va="center", fontsize=10)
    return _save(fig, "category_revenue.png")


def chart_segment_channel() -> Path:
    df = pd.read_sql("""
        SELECT c.segment, s.channel, SUM(f.total_amount) AS revenue
        FROM fact_order_items f
        JOIN dim_customer c ON f.customer_key = c.customer_key
        JOIN dim_store    s ON f.store_key   = s.store_key
        GROUP BY c.segment, s.channel
    """, get_engine())
    pivot = df.pivot(index="segment", columns="channel", values="revenue").fillna(0) / 1_000_000
    pivot = pivot.reindex(index=["NEW", "REGULAR", "VIP"])

    fig, ax = plt.subplots(figsize=(10, 5))
    pivot.plot(kind="bar", ax=ax, color=["#F18F01", "#2E86AB", "#3D9970"], width=0.7)
    ax.set_title("Revenue by Customer Segment × Channel", fontsize=14, fontweight="bold")
    ax.set_ylabel("Revenue ($M)")
    ax.set_xlabel("Segment")
    plt.xticks(rotation=0)
    ax.legend(title="Channel", loc="upper left")
    return _save(fig, "segment_channel.png")


def chart_status_distribution() -> Path:
    df = pd.read_sql("""
        SELECT order_status, COUNT(*) AS cnt
        FROM fact_order_items
        GROUP BY order_status
        ORDER BY cnt DESC
    """, get_engine())

    fig, ax = plt.subplots(figsize=(8, 8))
    colors = ["#3D9970", "#2E86AB", "#F18F01", "#A23B72", "#888888"]
    ax.pie(df["cnt"], labels=df["order_status"], autopct="%1.1f%%",
           startangle=90, colors=colors[:len(df)],
           wedgeprops={"edgecolor": "white", "linewidth": 2})
    ax.set_title("Order Status Distribution", fontsize=14, fontweight="bold")
    return _save(fig, "order_status.png")


def chart_top_products() -> Path:
    df = pd.read_sql("""
        SELECT p.name, p.category, SUM(f.total_amount) AS revenue
        FROM fact_order_items f
        JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.name, p.category
        ORDER BY revenue DESC
        LIMIT 15
    """, get_engine())
    df = df.iloc[::-1]
    df["short_name"] = df["name"].str.slice(0, 30) + (df["name"].str.len() > 30).map({True: "…", False: ""})

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh(df["short_name"], df["revenue"] / 1000, color="#2E86AB")
    ax.set_title("Top 15 Products by Revenue", fontsize=14, fontweight="bold")
    ax.set_xlabel("Revenue ($K)")
    return _save(fig, "top_products.png")


def main() -> None:
    print(f"writing dashboards to {OUT_DIR}/")
    for fn in (
        chart_monthly_revenue,
        chart_categories,
        chart_segment_channel,
        chart_status_distribution,
        chart_top_products,
    ):
        path = fn()
        print(f"  {path.name}")


if __name__ == "__main__":
    main()
