# Backend Layout

This backend is split into two layers on purpose:

- `app/` = the actual product app for Data-Berge OS
- `data_berge_core/` = reusable analytics/agent building blocks

## What lives in `app/`

`app/` is the application-specific layer. It knows about this product's API, database, files, runtime config, and local environment.

Put code here when it is tied to how Data-Berge OS runs today:

- FastAPI entrypoints and routes: `app/main.py`, `app/api/`
- SQLite/DuckDB/file handling: `app/storage/`, `app/services/`
- environment settings and startup hooks: `app/settings.py`
- local adapter implementations for core contracts: `app/adapters/`
- product workflows that connect upload, chat, and report flows: `app/workflows/`
- role wrappers that assemble skills into product-facing agents: `app/agents/`

In short: `app/` answers "how does this product run on this machine?"

## What lives in `data_berge_core/`

`data_berge_core/` is the reusable layer. It should contain logic we could plug into another app later without dragging along FastAPI routes or this project's storage details.

Put code here when it represents shared behavior or a stable contract:

- interfaces between runtime and skills: `contracts/`
- dataset context objects: `contracts/dataset.py`
- reusable skills such as intake, profiling, query, engineering, reporting, and visualization: `skills/`
- small runtime-level shared types: `runtime.py`

In short: `data_berge_core/` answers "what are the reusable analytics OS primitives?"

## Rule of thumb

If code needs to know about:

- HTTP routes
- the local database schema
- local file paths
- MLflow wiring specific to this app
- frontend-facing response shapes

it belongs in `app/`.

If code can survive as a reusable module with injected dependencies, it belongs in `data_berge_core/`.

## Current relationship

Today the flow is:

1. `app/` receives requests and loads local dataset/runtime state.
2. `app/adapters/` implements the contracts expected by the core package.
3. `app/agents/` assembles `TeamManagerAgent`, `DataAnalystAgent`, `DataEngineerAgent`, and `ReportAgent`.
4. those role agents use reusable skills from `data_berge_core/skills/`.

So the core package is the brain/toolbox, and `app/` is the product shell that wires it into a working backend.
