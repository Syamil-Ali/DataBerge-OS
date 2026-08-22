from __future__ import annotations

import socket

from rq import Queue, Worker

from app.settings import validate_runtime_config
from app.services.redis_runtime import redis_client
from app.storage.database import assert_schema_current


def main() -> None:
    validate_runtime_config()
    assert_schema_current()
    connection = redis_client()
    worker = Worker(
        [Queue("reports", connection=connection), Queue("connectors", connection=connection)],
        connection=connection,
        name=f"data-berge-worker-{socket.gethostname()}",
    )
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
