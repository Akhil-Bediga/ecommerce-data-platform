"""Generate fake e-commerce data and push it to S3.

Writes 4 CSVs (customers, products, stores, orders) that look like a daily
dump from an OLTP system, then uploads them to LocalStack S3.
"""
from __future__ import annotations

import argparse
import random
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import boto3
import numpy as np
import pandas as pd
from botocore.exceptions import ClientError
from faker import Faker
from tqdm import tqdm

from src.config import pipeline_cfg, s3_cfg

fake = Faker()
Faker.seed(42)
random.seed(42)
np.random.seed(42)

CATEGORIES = {
    "Electronics": ["Phones", "Laptops", "Headphones", "Cameras"],
    "Apparel": ["Shirts", "Shoes", "Jackets", "Accessories"],
    "Home": ["Kitchen", "Furniture", "Decor", "Bedding"],
    "Beauty": ["Skincare", "Makeup", "Haircare", "Fragrance"],
    "Sports": ["Outdoor", "Fitness", "Cycling", "Running"],
}
BRANDS = ["Acme", "Globex", "Initech", "Umbrella", "Soylent", "Stark", "Wayne"]
CHANNELS = ["ONLINE", "MOBILE", "RETAIL"]
REGIONS = ["NA", "EU", "APAC", "LATAM"]
ORDER_STATUSES = ["PLACED", "SHIPPED", "DELIVERED", "RETURNED", "CANCELLED"]
STATUS_WEIGHTS = [0.05, 0.10, 0.78, 0.04, 0.03]


def gen_customers(n: int) -> pd.DataFrame:
    return pd.DataFrame({
        "customer_id":  [str(uuid.uuid4()) for _ in range(n)],
        "first_name":   [fake.first_name() for _ in range(n)],
        "last_name":    [fake.last_name()  for _ in range(n)],
        "email":        [fake.unique.email() for _ in range(n)],
        "country":      [fake.country() for _ in range(n)],
        "city":         [fake.city() for _ in range(n)],
        "signup_date":  [fake.date_between(start_date="-3y", end_date="today") for _ in range(n)],
        "segment":      np.random.choice(["NEW", "REGULAR", "VIP"], size=n, p=[0.3, 0.6, 0.1]),
    })


def gen_products(n: int) -> pd.DataFrame:
    rows = []
    for _ in range(n):
        cat = random.choice(list(CATEGORIES.keys()))
        sub = random.choice(CATEGORIES[cat])
        rows.append({
            "product_id":  str(uuid.uuid4()),
            "name":        f"{random.choice(BRANDS)} {sub} {fake.word().title()}",
            "category":    cat,
            "subcategory": sub,
            "brand":       random.choice(BRANDS),
            "base_price":  round(random.uniform(5, 1500), 2),
        })
    return pd.DataFrame(rows)


def gen_stores(n: int = 25) -> pd.DataFrame:
    return pd.DataFrame({
        "store_id":  [str(uuid.uuid4()) for _ in range(n)],
        "name":      [f"Store-{i:03d}" for i in range(n)],
        "region":    [random.choice(REGIONS) for _ in range(n)],
        "country":   [fake.country() for _ in range(n)],
        "channel":   [random.choice(CHANNELS) for _ in range(n)],
    })


def gen_orders(
    n_rows: int,
    customer_ids: np.ndarray,
    products: pd.DataFrame,
    store_ids: np.ndarray,
    days_back: int = 90,
) -> pd.DataFrame:
    """Order line items - n_rows is the number of fact rows."""
    today = date.today()
    order_dates = [
        today - timedelta(days=random.randint(0, days_back))
        for _ in range(n_rows)
    ]
    # share order_ids across rows so we get ~3 line items per order on avg
    n_orders = max(1, n_rows // 3)
    order_pool = [str(uuid.uuid4()) for _ in range(n_orders)]
    chosen_orders = np.random.choice(order_pool, size=n_rows)

    chosen_products = products.sample(n=n_rows, replace=True).reset_index(drop=True)
    quantities = np.random.randint(1, 6, size=n_rows)
    discounts = np.where(
        np.random.random(n_rows) < 0.2,
        np.round(np.random.uniform(1, 50, size=n_rows), 2),
        0.0,
    )
    unit_prices = chosen_products["base_price"].to_numpy()
    totals = np.maximum(unit_prices * quantities - discounts, 0).round(2)

    return pd.DataFrame({
        "order_id":        chosen_orders,
        "customer_id":     np.random.choice(customer_ids, size=n_rows),
        "product_id":      chosen_products["product_id"].to_numpy(),
        "store_id":        np.random.choice(store_ids, size=n_rows),
        "order_date":      order_dates,
        "quantity":        quantities,
        "unit_price":      unit_prices,
        "discount_amount": discounts,
        "total_amount":    totals,
        "order_status":    np.random.choice(ORDER_STATUSES, size=n_rows, p=STATUS_WEIGHTS),
        "created_at":      [datetime.now() for _ in range(n_rows)],
    })


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=s3_cfg.endpoint_url,
        region_name=s3_cfg.region,
        aws_access_key_id=s3_cfg.access_key,
        aws_secret_access_key=s3_cfg.secret_key,
    )


def ensure_bucket(s3) -> None:
    try:
        s3.head_bucket(Bucket=s3_cfg.bucket)
    except ClientError:
        s3.create_bucket(Bucket=s3_cfg.bucket)


def upload(s3, local_path: Path, key: str) -> None:
    s3.upload_file(str(local_path), s3_cfg.bucket, key)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=100_000,
                        help="Number of order line items (fact rows).")
    parser.add_argument("--customers", type=int, default=5_000)
    parser.add_argument("--products", type=int, default=2_000)
    parser.add_argument("--no-upload", action="store_true",
                        help="Skip uploading to S3.")
    args = parser.parse_args()

    raw_dir = pipeline_cfg.data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    print(f"generating {args.customers:,} customers")
    customers = gen_customers(args.customers)
    customers.to_csv(raw_dir / "customers.csv", index=False)

    print(f"generating {args.products:,} products")
    products = gen_products(args.products)
    products.to_csv(raw_dir / "products.csv", index=False)

    print("generating stores")
    stores = gen_stores()
    stores.to_csv(raw_dir / "stores.csv", index=False)

    print(f"generating {args.rows:,} order line items")
    orders = gen_orders(
        n_rows=args.rows,
        customer_ids=customers["customer_id"].to_numpy(),
        products=products,
        store_ids=stores["store_id"].to_numpy(),
    )
    orders.to_csv(raw_dir / "orders.csv", index=False)

    print(f"wrote raw CSVs to {raw_dir}")

    if args.no_upload:
        return

    print(f"uploading to s3://{s3_cfg.bucket}/{s3_cfg.prefix}/")
    s3 = s3_client()
    ensure_bucket(s3)
    for fname in tqdm(["customers.csv", "products.csv", "stores.csv", "orders.csv"]):
        upload(s3, raw_dir / fname, f"{s3_cfg.prefix}/{fname}")
    print("upload done")


if __name__ == "__main__":
    main()
