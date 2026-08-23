from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "Data-Berge OS")
APP_ENV = os.getenv("APP_ENV", "local")
IS_PRODUCTION = APP_ENV.strip().lower() in {"production", "prod"}
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DATABASE_POOL_MIN = max(1, int(os.getenv("DATABASE_POOL_MIN", "2")))
DATABASE_POOL_MAX = max(DATABASE_POOL_MIN, int(os.getenv("DATABASE_POOL_MAX", "10")))
REDIS_URL = os.getenv("REDIS_URL", "").strip()
QUEUE_MODE = os.getenv("QUEUE_MODE", "local").strip().lower()
OBJECT_STORAGE_BACKEND = os.getenv(
    "OBJECT_STORAGE_BACKEND", "local"
).strip().lower()
S3_BUCKET = os.getenv("S3_BUCKET", "").strip()
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "").strip() or None
S3_REGION = os.getenv("S3_REGION", "us-east-1").strip()
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "").strip() or None
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "").strip() or None
S3_PREFIX = os.getenv("S3_PREFIX", "data-berge").strip().strip("/")
LOCAL_CACHE_DIR_NAME = os.getenv("LOCAL_CACHE_DIR_NAME", "cache").strip()
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
RUN_STARTUP_RECONCILIATION = os.getenv(
    "RUN_STARTUP_RECONCILIATION", "false" if IS_PRODUCTION else "true"
).lower() in {"1", "true", "yes", "on"}
AUTO_MIGRATE = os.getenv("AUTO_MIGRATE", "false" if IS_PRODUCTION else "true").lower() in {
    "1", "true", "yes", "on"
}
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production-use-openssl-rand-hex-32")
JWT_ISSUER = os.getenv("JWT_ISSUER", "data-berge-os")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "data-berge-web")
TOKEN_EXPIRE_MINUTES = max(5, int(os.getenv("TOKEN_EXPIRE_MINUTES", "60")))
AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "db_session")
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "db_csrf")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true" if IS_PRODUCTION else "false").lower() in {"1", "true", "yes", "on"}
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN") or None
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "false").lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "*").split(",") if host.strip()]
AUTH_RATE_LIMIT_REQUESTS = max(1, int(os.getenv("AUTH_RATE_LIMIT_REQUESTS", "10")))
AUTH_RATE_LIMIT_WINDOW_SECONDS = max(1, int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60")))
MAX_UPLOAD_BYTES = max(1024, int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))))
MAX_REQUEST_BODY_BYTES = max(
    MAX_UPLOAD_BYTES,
    int(os.getenv("MAX_REQUEST_BODY_BYTES", str(MAX_UPLOAD_BYTES + 1024 * 1024))),
)
MAX_WORKBOOK_UNCOMPRESSED_BYTES = max(
    MAX_UPLOAD_BYTES,
    int(os.getenv("MAX_WORKBOOK_UNCOMPRESSED_BYTES", str(100 * 1024 * 1024))),
)
MAX_STORAGE_BYTES = max(MAX_UPLOAD_BYTES, int(os.getenv("MAX_STORAGE_BYTES", str(100 * 1024 * 1024))))
REPORT_WORKERS = max(1, int(os.getenv("REPORT_WORKERS", "2")))
REPORT_QUEUE_CAPACITY = max(REPORT_WORKERS, int(os.getenv("REPORT_QUEUE_CAPACITY", "10")))
CONNECTOR_WORKERS = max(1, int(os.getenv("CONNECTOR_WORKERS", "2")))
CONNECTOR_QUEUE_CAPACITY = max(CONNECTOR_WORKERS, int(os.getenv("CONNECTOR_QUEUE_CAPACITY", "6")))
OPENDOSM_MAX_ROWS = max(1_000, int(os.getenv("OPENDOSM_MAX_ROWS", "250000")))
AGNO_MODEL = os.getenv("AGNO_MODEL", "openai:gpt-5.5")
AGNO_API_KEY = os.getenv("AGNO_API_KEY")
AGNO_BASE_URL = os.getenv("AGNO_BASE_URL")
AGNO_REQUEST_TIMEOUT_SECONDS = max(5.0, float(os.getenv("AGNO_REQUEST_TIMEOUT_SECONDS", "45")))
AGNO_MAX_RETRIES = max(0, int(os.getenv("AGNO_MAX_RETRIES", "0")))
MLFLOW_TRACKING_ENABLED = os.getenv("MLFLOW_TRACKING_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
MLFLOW_EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "Data-Berge OS")
MLFLOW_LOG_PROMPT_INSTANCES = os.getenv("MLFLOW_LOG_PROMPT_INSTANCES", "false").lower() in {"1", "true", "yes", "on"}
MLFLOW_PROMPT_VERSION = os.getenv("MLFLOW_PROMPT_VERSION", "query-analyst-v1")
MLFLOW_QUERY_ANALYST_PROMPT_NAME = os.getenv("MLFLOW_QUERY_ANALYST_PROMPT_NAME", "query-analyst-planner")
MLFLOW_QUERY_ANALYST_PROMPT_VERSION = os.getenv("MLFLOW_QUERY_ANALYST_PROMPT_VERSION", "1")
OBSERVABILITY_ID_SECRET = os.getenv("OBSERVABILITY_ID_SECRET", "")

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = (BACKEND_DIR / os.getenv("DATA_DIR", "../data")).resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
ARTIFACT_DIR = DATA_DIR / "artifacts"
CACHE_DIR = DATA_DIR / LOCAL_CACHE_DIR_NAME
DB_PATH = (BACKEND_DIR / os.getenv("DB_PATH", "../data/app.db")).resolve()

for path in (DATA_DIR, UPLOAD_DIR, ARTIFACT_DIR, CACHE_DIR, DB_PATH.parent):
    path.mkdir(parents=True, exist_ok=True)


def cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://localhost:3000")
    if raw.strip() == "*":
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def validate_runtime_config() -> None:
    """Fail closed when a production deployment uses unsafe defaults."""
    errors: list[str] = []
    if COOKIE_SAMESITE not in {"lax", "strict", "none"}:
        errors.append("COOKIE_SAMESITE must be one of: lax, strict, none")
    if COOKIE_SAMESITE == "none" and not COOKIE_SECURE:
        errors.append("COOKIE_SECURE must be true when COOKIE_SAMESITE=none")
    if MAX_REQUEST_BODY_BYTES < MAX_UPLOAD_BYTES:
        errors.append("MAX_REQUEST_BODY_BYTES cannot be lower than MAX_UPLOAD_BYTES")
    if QUEUE_MODE not in {"local", "redis"}:
        errors.append("QUEUE_MODE must be local or redis")
    if OBJECT_STORAGE_BACKEND not in {"local", "s3"}:
        errors.append("OBJECT_STORAGE_BACKEND must be local or s3")
    if errors:
        raise RuntimeError("Unsafe runtime configuration: " + "; ".join(errors))
