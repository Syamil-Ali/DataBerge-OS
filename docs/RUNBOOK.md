# Production Runbook

## Supported topology

Production requires:

- two or more stateless API replicas;
- one or more worker replicas;
- managed PostgreSQL;
- managed Redis with persistence and a no-eviction policy;
- versioned S3-compatible object storage;
- a separately served frontend using the same-origin /api proxy.

SQLite and local file storage are development adapters and are rejected by production validation.

## Release gate

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
~~~

CI also runs Chromium E2E, a real PostgreSQL/Redis/MinIO integration test, migration verification and both production image builds.

## Local distributed stack

~~~powershell
docker compose up -d
docker compose ps
~~~

The stack exposes the frontend on 8080, API on 8000, PostgreSQL on 15432, Redis on 6380 and MinIO API/console on 9000/9001. The migrate service must complete before API and worker services start.

## Production configuration

Copy backend/.env.production.example into the secret manager. Required values include:

- DATABASE_URL for PostgreSQL;
- REDIS_URL and QUEUE_MODE=redis;
- OBJECT_STORAGE_BACKEND=s3, S3_BUCKET, region/endpoint and credentials;
- a unique JWT_SECRET of at least 32 random bytes;
- explicit CORS_ALLOW_ORIGINS and ALLOWED_HOSTS;
- COOKIE_SECURE=true;
- AUTO_MIGRATE=false;
- stable OBSERVABILITY_ID_SECRET;
- OTEL_EXPORTER_OTLP_ENDPOINT when distributed tracing is enabled.

The API refuses to start if distributed production dependencies are absent.

## Deployment sequence

1. Build one immutable backend image and one frontend image.
2. Back up PostgreSQL and verify object-store versioning/retention.
3. Run python -m scripts.migrate exactly once as the pre-deploy command.
4. Start or roll worker replicas.
5. Roll API replicas while keeping at least one ready instance.
6. Roll the frontend.
7. Verify readiness, metrics, an authenticated upload and a worker-generated report.

Railway uses backend/railway.json for the API and backend/railway.worker.json for the worker. Both services use the same image and environment. The worker is private; only the frontend needs public ingress when using the /api proxy.

## Health and telemetry

- GET /api/health/live: process liveness.
- GET /api/health/ready: PostgreSQL, migration version, Redis, S3 and cache readiness.
- GET /metrics: Prometheus request and queue metrics.
- GET /healthz on the frontend: static server health.

Alert on:

- readiness failures for two consecutive checks;
- API 5xx above 1 percent for five minutes;
- p95 API latency above 750 ms for ten minutes;
- report or connector queue depth above 20 for ten minutes;
- oldest queued job above five minutes;
- PostgreSQL pool exhaustion;
- object-store or Redis errors;
- worker failure/retry spikes.

## Scaling

API replicas are stateless and may be increased independently. Start with two replicas and scale on sustained 65 percent CPU or 75 percent memory. Workers scale on Redis queue depth, targeting roughly two waiting jobs per worker. Use a five-minute downscale stabilization period to avoid flapping.

Kubernetes reference policies are in deploy/kubernetes/autoscaling.yaml. On Railway, apply the same thresholds through monitoring and adjust API/worker replica counts independently.

Run the capacity test before raising published limits:

~~~powershell
k6 run -e BASE_URL=https://app.example.com/api -e TEST_EMAIL=load@example.com -e TEST_PASSWORD=secret tests/load/distributed_capacity.js
~~~

## Backup and recovery

PostgreSQL:

1. Enable managed point-in-time recovery.
2. Take a logical backup before schema migrations.
3. Restore into a new database for monthly verification.
4. Change DATABASE_URL only after integrity and smoke checks pass.

Object storage:

1. Enable bucket versioning and lifecycle rules.
2. Replicate or back up to a separate failure domain.
3. Verify a sampled object restore monthly.
4. Never treat a node-local cache as a backup.

Redis queues:

1. Enable persistence appropriate to the managed provider.
2. Keep maxmemory-policy=noeviction.
3. PostgreSQL background_jobs remains the user-visible status record if Redis must be rebuilt.

The SQLite scripts.db_admin command remains for local-development databases only.

## Rollback

1. Stop migrations and new releases.
2. Roll API, workers and frontend back to the last image that passed CI.
3. Do not reverse an applied schema manually. Restore the pre-migration PostgreSQL backup when a schema rollback is required.
4. Preserve S3 objects; use object versions rather than deleting current data.
5. Wait for all API replicas to become ready.
6. Run authenticated upload, cross-replica read and worker report checks.
7. Inspect request-ID-correlated logs, traces and queue depth.

## Incident notes

- API restarts do not lose queued RQ jobs.
- Worker failures are retried and reflected in durable background-job/artifact status.
- Queue saturation returns HTTP 503 instead of accepting unbounded work.
- HTTP 413 indicates request, archive-expansion or storage-quota enforcement.
- Every response and structured request log carries X-Request-ID.
