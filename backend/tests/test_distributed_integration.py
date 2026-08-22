from __future__ import annotations

import os
import tempfile
import unittest
import uuid
from pathlib import Path


@unittest.skipUnless(os.getenv("RUN_DISTRIBUTED_TESTS") == "1", "distributed services not enabled")
class DistributedIntegrationTests(unittest.TestCase):
    def test_postgres_s3_redis_and_durable_queue_contract(self) -> None:
        from app.middleware.production import RedisRateLimiter
        from app.services.job_queue import enqueue
        from app.services.redis_runtime import redis_client
        from app.storage import database
        from app.storage.object_store import (
            get_object_store,
            materialize_path,
            persist_file,
            reset_object_store,
        )

        database.init_db()
        reset_object_store()
        unique = uuid.uuid4().hex
        email = f"integration-{unique}@example.com"
        user = database.create_user(email, "Integration", "hash")
        project = database.create_project_for_user(user["id"], "Distributed integration")
        namespace = f"integration-{unique}"
        job_id = f"integration-{unique}"
        try:
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "sample.csv"
                source.write_text("amount\n10\n20\n", encoding="utf-8")
                uri = persist_file(
                    source,
                    user_id=user["id"],
                    namespace=namespace,
                )
                self.assertTrue(uri.startswith("s3://"))
                self.assertEqual(get_object_store().size(uri), source.stat().st_size)
                materialized = materialize_path(uri)
                self.assertEqual(materialized.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))
                self.assertGreater(
                    get_object_store().namespace_usage(user_id=user["id"], namespace=namespace),
                    0,
                )

            dataset_record = {
                "id": f"dataset-{unique}",
                "project_id": project["id"],
                "name": "First materialization",
                "original_filename": "sample.csv",
                "file_type": "csv",
                "source_path": uri,
                "working_path": uri,
                "row_count": 2,
                "column_count": 1,
                "status": "profiled",
                "profile": {"row_count": 2, "column_count": 1},
            }
            database.replace_dataset_for_user(user["id"], dataset_record)
            dataset_record["name"] = "Replacement materialization"
            replaced = database.replace_dataset_for_user(user["id"], dataset_record)
            self.assertEqual(replaced["name"], "Replacement materialization")
            with database.connect() as connection:
                count = connection.execute(
                    "select count(*) as count from datasets where id = ?",
                    (dataset_record["id"],),
                ).fetchone()
            self.assertEqual(int(count["count"]), 1)

            job = database.create_background_job(
                user["id"],
                queue="integration",
                kind="probe",
                payload={"value": 1},
                job_id=job_id,
            )
            self.assertEqual(job["status"], "queued")
            updated = database.update_background_job(
                user["id"],
                job_id,
                status="completed",
                message="Done",
                result={"ok": True},
            )
            self.assertEqual(updated["result"], {"ok": True})

            limiter = RedisRateLimiter(limit=2, window_seconds=30)
            key = f"integration:{unique}"
            self.assertTrue(limiter.allow(key)[0])
            self.assertTrue(limiter.allow(key)[0])
            self.assertFalse(limiter.allow(key)[0])

            enqueue(
                "integration",
                len,
                [1, 2, 3],
                job_id=f"rq-{unique}",
                capacity=10,
                timeout_seconds=30,
            )
            self.assertIsNotNone(redis_client().hgetall(f"rq:job:rq-{unique}"))

            ready = database.health_check()
            self.assertEqual(ready["database"], "ok")
            self.assertEqual(ready["journal_mode"], "postgresql")
            self.assertEqual(ready["redis"], "ok")
        finally:
            get_object_store().delete_namespace(user_id=user["id"], namespace=namespace)
            redis_client().delete(f"rate-limit:integration:{unique}", f"rq:job:rq-{unique}")
            with database.connect() as connection:
                connection.execute("delete from users where id = ?", (user["id"],))
