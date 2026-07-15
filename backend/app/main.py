from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import artifacts, auth, chat, chat_sessions, datasets, opendosm, projects, relational, reports
from app.services.llm_observability import configure_agno_autolog
from app.settings import APP_NAME, cors_origins
from app.storage.database import init_db

app = FastAPI(title=APP_NAME, version="0.1.0")

origins = cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    configure_agno_autolog()


@app.get("/api/health")
def health():
    return {"status": "ok", "app": APP_NAME}


app.include_router(projects.router, prefix="/api")
app.include_router(datasets.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(artifacts.router, prefix="/api")
app.include_router(chat_sessions.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(opendosm.router, prefix="/api")
app.include_router(relational.router, prefix="/api")
