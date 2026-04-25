import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class MySQLConfig:
    host: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    port: int = int(os.getenv("MYSQL_PORT", "3306"))
    user: str = os.getenv("MYSQL_USER", "ecom_user")
    password: str = os.getenv("MYSQL_PASSWORD", "ecom_pass")
    database: str = os.getenv("MYSQL_DATABASE", "ecommerce")

    @property
    def url(self) -> str:
        return (
            f"mysql+pymysql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}?charset=utf8mb4"
        )


@dataclass(frozen=True)
class S3Config:
    endpoint_url: str = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    region: str = os.getenv("AWS_REGION", "us-east-1")
    access_key: str = os.getenv("AWS_ACCESS_KEY_ID", "test")
    secret_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
    bucket: str = os.getenv("S3_BUCKET", "ecom-raw")
    prefix: str = os.getenv("S3_PREFIX", "orders")


@dataclass(frozen=True)
class PipelineConfig:
    data_dir: Path = PROJECT_ROOT / os.getenv("DATA_DIR", "data").lstrip("./")
    batch_size: int = int(os.getenv("BATCH_SIZE", "10000"))


mysql_cfg = MySQLConfig()
s3_cfg = S3Config()
pipeline_cfg = PipelineConfig()
