from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from src.config import mysql_cfg


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(
        mysql_cfg.url,
        pool_pre_ping=True,
        pool_recycle=3600,
        future=True,
    )
