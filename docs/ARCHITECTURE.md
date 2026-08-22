# Architecture

## Product boundary

Data-Berge OS is a governed file-analytics modular monolith. Production runs separate stateless API and durable worker processes backed by PostgreSQL, Redis, and S3-compatible object storage. The frontend serves static assets and proxies /api to the API service.

## Runtime topology

~~~text
Browser
  |
Frontend / same-origin proxy
  |
Stateless FastAPI replicas
  |-------- PostgreSQL metadata and durable job status
  |-------- Redis global rate limits and RQ queues
  |-------- S3 datasets and generated working files
                 |
          Report / connector workers
~~~

API replicas do authentication, validation, orchestration and fast reads. Workers execute report generation and external connector jobs. Any replica or worker materializes an S3 object into its own disposable, content-addressed cache only when analytics needs a local file.

## Runtime layers

- backend/app/main.py owns the HTTP and health surface.
- backend/app/middleware owns CSRF, shared rate limiting, security headers, request IDs and request logs.
- backend/app/storage/connections.py owns pooled PostgreSQL and local SQLite connections.
- backend/app/storage/postgres_schema.py and numbered migrations own schema creation.
- backend/app/storage/object_store.py owns local and S3-compatible file persistence.
- backend/app/storage/account_repository.py, job_repository.py and relational_repository.py isolate metadata domains behind the stable database facade.
- backend/app/services/job_queue.py and scripts/worker.py own durable RQ execution.
- backend/app/services/telemetry.py exports Prometheus metrics and optional OTLP traces.
- backend/app/workflows owns upload, chat and report transactions.
- backend/data_berge_core contains reusable deterministic analytics contracts and skills.
- frontend feature modules own routing, relationship modeling, reporting and workspace presentation.

## Security boundary

Browser authentication uses short-lived JWTs in Secure, HttpOnly cookies plus a separate CSRF token. Bearer tokens remain available for non-browser clients. Redis applies authentication limits across all replicas. Production startup fails if PostgreSQL, Redis, S3, secrets, origins, hosts or secure cookies are not configured.

Every user-owned metadata query includes ownership criteria. Object keys are namespaced by user and dataset. Uploads are streamed under compressed-size limits, workbook expansion is bounded and quota reservations are atomic.

## Persistence boundary

PostgreSQL is authoritative for users, projects, datasets, chat, artifacts, schemas, quota counters and durable job status. Migrations run once as a pre-deploy operation; API and worker processes verify the schema rather than racing to modify it.

S3-compatible storage is authoritative for uploaded and generated tabular files. Node-local cache data is disposable. Redis is durable queue and shared limiter state, configured with a no-eviction policy for the self-hosted topology.

SQLite and local files remain a development/test adapter only.

## Agent boundary

The LLM chooses typed orchestration decisions. Deterministic profiling, SELECT-only queries, engineering and reporting services produce the evidence. DataAnalyst routing is separated from investigation logic, and background execution is outside the API failure domain.

## Scaling model

- API replicas scale on CPU and memory.
- Worker replicas scale on the Redis reports and connectors queue depths.
- PostgreSQL connections are bounded per process.
- Queue capacity, upload size, workbook expansion and user storage limits provide backpressure.
- S3 removes replica affinity.

Reference Kubernetes HPA/KEDA policies live in deploy/kubernetes/autoscaling.yaml. Railway deployments use separate API and worker services and can increase replicas independently.

## Operations

- /api/health/live checks process liveness.
- /api/health/ready checks PostgreSQL migration state, Redis, S3 and local cache writability.
- /metrics exports request latency, status, in-flight requests and queue depth.
- OTEL_EXPORTER_OTLP_ENDPOINT enables distributed tracing.
- CI runs local tests, frontend tests, browser tests, dependency audits, real PostgreSQL/Redis/MinIO integration and both image builds.

Remaining enterprise extensions are fine-grained RBAC, append-only audit events, lifecycle/retention policies and region-level disaster recovery.
