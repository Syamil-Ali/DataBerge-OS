from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api import artifacts, auth, chat, chat_sessions, connections, datasets, opendosm, projects, relational, reports
from app.middleware.production import ProductionMiddleware, RequestBodyLimitMiddleware
from app.services.llm_observability import configure_agno_autolog
from app.services.report_queue import shutdown_report_queue
from app.api.opendosm import shutdown_connector_queue
from app.settings import ALLOWED_HOSTS, APP_NAME, MAX_REQUEST_BODY_BYTES, cors_origins, validate_runtime_config
from app import settings
from app.storage.database import assert_schema_current, health_check, init_db, reconcile_storage_usage, recover_interrupted_jobs
from app.storage.connections import close_pool, uses_postgres
from app.services.redis_runtime import close_redis
from app.services.telemetry import configure_telemetry


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_runtime_config()
    logging.getLogger("data_berge.http").setLevel(logging.INFO)
    # Railway mounts persistent volumes only for the deployed container, not the
    # pre-deploy command. A local SQLite database must therefore be initialized
    # after the volume is mounted. PostgreSQL can still use the pre-deploy gate.
    if settings.AUTO_MIGRATE or not uses_postgres():
        init_db()
    else:
        assert_schema_current()
    if settings.RUN_STARTUP_RECONCILIATION:
        reconcile_storage_usage()
    recover_interrupted_jobs()
    configure_agno_autolog()
    yield
    shutdown_report_queue()
    shutdown_connector_queue()
    close_redis()
    close_pool()


app = FastAPI(title=APP_NAME, version="0.2.0", lifespan=lifespan)
configure_telemetry(app)

origins = cors_origins()
app.add_middleware(ProductionMiddleware)
app.add_middleware(RequestBodyLimitMiddleware, max_bytes=MAX_REQUEST_BODY_BYTES)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": APP_NAME}


@app.get("/api/health/live")
def liveness():
    return {"status": "ok"}


@app.get("/api/health/ready")
def readiness():
    return health_check()


app.include_router(projects.router, prefix="/api")
app.include_router(datasets.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(artifacts.router, prefix="/api")
app.include_router(chat_sessions.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(opendosm.router, prefix="/api")
app.include_router(relational.router, prefix="/api")
app.include_router(connections.router, prefix="/api")
