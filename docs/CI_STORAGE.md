# Distributed CI storage

The distributed-integration job uses `docker-compose.ci.yml`, not the shared
deployment Compose file. It runs real PostgreSQL and Redis and the official
version-pinned Moto server as an S3 HTTP emulator. Startup waits for all three
health checks, then the runner creates and checks a disposable bucket using
the existing boto3 dependency before migrations and integration tests.

The dedicated `data-berge-ci` Compose project has no shared named data volumes
and binds exposed ports only to loopback. Use on a clean runner; the ports
15432, 6380 and 9000 must be free. Failure logs and cleanup use the same file
and project, so they do not target deployment services.

Moto is test infrastructure, not production object storage. This job tests the
application's S3 client contract, not production IAM, durability, TLS or vendor
compatibility. Those require separate checks against the production provider.
The production/shared `docker-compose.yml` and application storage code are
unchanged; this change does not repair that file's unavailable MinIO images.

Start services: `docker compose -f docker-compose.ci.yml up -d --wait --wait-timeout 120`.
Use the distributed-integration job's environment and bucket setup, then run
`python -m scripts.migrate` and
`python -m unittest tests.test_distributed_integration -v` from `backend`.
After testing, `docker compose -f docker-compose.ci.yml down -v` removes only
the disposable CI project's containers, network and volumes.

Official image documentation: https://docs.getmoto.org/en/5.1.3/docs/server_mode.html
