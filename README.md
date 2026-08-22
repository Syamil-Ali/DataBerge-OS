# Data-Berge OS

Data-Berge OS is a multi-tenant analytics operating system for business teams. It turns CSV/XLSX and OpenDOSM data into governed profiles, queryable workspaces, charts, and approval-based executive reports.

## Production architecture

- Stateless FastAPI replicas use pooled PostgreSQL for metadata and tenant-scoped transactions.
- S3-compatible object storage owns uploads and generated working files; each API or worker uses only a disposable content-addressed cache.
- Redis provides shared authentication rate limits and durable RQ queues.
- Separate workers run report and connector jobs, with retry and durable job status.
- Prometheus metrics and optional OpenTelemetry export cover HTTP traffic and queue depth.
- Kubernetes HPA and KEDA examples scale API replicas and workers independently.

SQLite, local files, in-process queues, and in-memory rate limits remain convenient development adapters. Production validation rejects those adapters and unsafe cookie, origin, host, and secret settings.

## Local development

~~~powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env
cd ..
python run.py
~~~

This starts the backend at http://127.0.0.1:8000 and the frontend at http://127.0.0.1:5173.

## Distributed development stack

~~~powershell
docker compose up --build
~~~

Open http://localhost:8080. Compose runs PostgreSQL, Redis, MinIO, a one-shot migration, stateless API, a separate worker, and the frontend. Named volumes belong only to PostgreSQL, Redis, and MinIO.

## Release validation

~~~powershell
cd backend
.venv\Scripts\python.exe -m compileall -q app data_berge_core scripts
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m pip check

cd ..\frontend
npm ci
npm audit --audit-level=high
npm run test:run
npm run build
npm run test:e2e
~~~

CI also runs the PostgreSQL/Redis/S3/RQ integration suite and builds both containers. See [the architecture](docs/ARCHITECTURE.md) and [production runbook](docs/RUNBOOK.md).
