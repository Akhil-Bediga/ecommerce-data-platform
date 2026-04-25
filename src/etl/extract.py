"""Pull raw CSVs from S3 into pandas DataFrames."""
from __future__ import annotations

import io
from dataclasses import dataclass

import boto3
import pandas as pd

from src.config import s3_cfg


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=s3_cfg.endpoint_url,
        region_name=s3_cfg.region,
        aws_access_key_id=s3_cfg.access_key,
        aws_secret_access_key=s3_cfg.secret_key,
    )


def _read_csv(s3, key: str) -> pd.DataFrame:
    obj = s3.get_object(Bucket=s3_cfg.bucket, Key=key)
    return pd.read_csv(io.BytesIO(obj["Body"].read()))


@dataclass
class RawData:
    customers: pd.DataFrame
    products: pd.DataFrame
    stores: pd.DataFrame
    orders: pd.DataFrame


def extract() -> RawData:
    s3 = _s3_client()
    prefix = s3_cfg.prefix
    print(f"      reading s3://{s3_cfg.bucket}/{prefix}/*.csv")
    return RawData(
        customers=_read_csv(s3, f"{prefix}/customers.csv"),
        products=_read_csv(s3, f"{prefix}/products.csv"),
        stores=_read_csv(s3, f"{prefix}/stores.csv"),
        orders=_read_csv(s3, f"{prefix}/orders.csv"),
    )
