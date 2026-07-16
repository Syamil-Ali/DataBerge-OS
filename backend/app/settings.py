from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "Data-Berge OS")
APP_ENV = os.getenv("APP_ENV", "local")
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
DB_PATH = (BACKEND_DIR / os.getenv("DB_PATH", "../data/app.db")).resolve()

for path in (DATA_DIR, UPLOAD_DIR, ARTIFACT_DIR, DB_PATH.parent):
    path.mkdir(parents=True, exist_ok=True)


def cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://localhost:3000")
    if raw.strip() == "*":
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]
