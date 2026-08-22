from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from app.services import files
from app.storage import database
from scripts.db_admin import backup, integrity, restore


class StorageResilienceTests(unittest.TestCase):
    def test_upload_stream_aborts_and_removes_partial_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "large.csv"
            with self.assertRaisesRegex(ValueError, "exceeds"):
                files.copy_upload_limited(io.BytesIO(b"12345"), target, max_bytes=4)
            self.assertFalse(target.exists())

    def test_workbook_expansion_limit_rejects_archive_bomb_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "large.xlsx"
            with zipfile.ZipFile(workbook, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("xl/worksheets/sheet1.xml", "x" * 128)
            with patch.object(files, "MAX_WORKBOOK_UNCOMPRESSED_BYTES", 64):
                with self.assertRaisesRegex(ValueError, "expands beyond"):
                    files.validate_workbook_archive(workbook)

    def test_migrations_backup_restore_and_interrupted_job_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            database, "DB_PATH", Path(directory) / "app.db"
        ):
            database.init_db()
            with database.connect() as conn:
                versions = [row["version"] for row in conn.execute(
                    "select version from schema_migrations order by version"
                ).fetchall()]
            self.assertEqual(versions, [1, 2, 3])

            user = database.create_user("owner@example.com", "Owner", "hash")
            project = database.create_project_for_user(user["id"], "Workspace")
            artifact = database.create_artifact(
                project["id"],
                "report",
                "Generating",
                {"report_progress": {"status": "running"}},
                status="generating",
                user_id=user["id"],
            )
            self.assertEqual(database.recover_interrupted_jobs(), 1)
            recovered = database.get_artifact_for_user(user["id"], project["id"], artifact["id"])
            self.assertEqual(recovered["status"], "failed")

            backup_path = Path(directory) / "backup.db"
            backup(database.DB_PATH, backup_path)
            self.assertEqual(integrity(backup_path), "ok")

            with database.connect() as conn:
                conn.execute("delete from projects")
            restored, safety = restore(backup_path, database.DB_PATH, confirmed=True)
            self.assertEqual(restored, database.DB_PATH.resolve())
            self.assertIsNotNone(safety)
            self.assertEqual(integrity(database.DB_PATH), "ok")

    def test_storage_reservation_is_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            database, "DB_PATH", Path(directory) / "app.db"
        ), patch.object(database, "MAX_STORAGE_BYTES", 10):
            database.init_db()
            user = database.create_user("quota@example.com", "Quota", "hash")
            self.assertTrue(database.reserve_user_storage(user["id"], 8))
            self.assertFalse(database.reserve_user_storage(user["id"], 3))
            self.assertEqual(database.get_user_storage(user["id"]), 8)


if __name__ == "__main__":
    unittest.main()
