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

## Supabase federated connector

The Supabase source uses PostgreSQL directly and does not download the selected table. Configure `CONNECTOR_SECRET_KEY` with a stable, high-entropy value before saving connections; changing it makes existing saved credentials unreadable. Query behavior is controlled by:

- `FEDERATED_CONNECT_TIMEOUT_SECONDS` (default `10`)
- `FEDERATED_QUERY_TIMEOUT_MS` (default `15000`)
- `FEDERATED_PREVIEW_ROWS` (default `100`)
- `FEDERATED_MAX_RESULT_ROWS` (default `500`)

Use a dedicated database user with `CONNECT`, schema `USAGE`, and `SELECT` only on the schemas and tables Data-Berge may access. The connector rejects private/local destination addresses, requires TLS, runs read-only transactions, and only permits a single query against the registered logical `dataset` table.

The initial scope is one table or view per federated dataset. Cross-table joins, writes, full materialization, scheduled sync, and per-user Supabase RLS forwarding are intentionally excluded.
