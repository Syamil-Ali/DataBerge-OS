# Backend layout

The backend separates product orchestration from reusable analytics behavior.

## Product layer: `app/`

This layer owns runtime and delivery concerns:

- `api/` — FastAPI routes and tenant authorization
- `workflows/` — upload, chat, and report use cases
- `storage/` — PostgreSQL/SQLite repositories and S3/local object adapters
- `services/` — Redis, queues, telemetry, profiling, and query execution
- `agents/` — product-facing agent composition and routing
- `adapters/` — implementations of the core package contracts

Repository modules are separated by domain while `storage/database.py` remains a compatibility facade. Long agent routing and frontend feature code are split into focused modules.

## Reusable layer: `data_berge_core/`

This package contains storage-agnostic analytics primitives:

- contracts and dataset contexts
- intake, profiling, query, engineering, governance, reporting, and visualization skills
- typed assignments, runtime types, memory, and shared tools

Code belongs here when it can operate through injected contracts without knowing about FastAPI, PostgreSQL, S3, Redis, or frontend response shapes.

## Runtime processes

- API: `uvicorn app.main:app`
- migrations: `python -m scripts.migrate`
- workers: `python -m scripts.worker`

Production runs migrations as a release step, then starts any number of stateless API replicas and independently scaled workers.
