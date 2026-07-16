from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.storage import database


class DatasetDeletionTests(unittest.TestCase):
    def test_user_dataset_deletion_preserves_reports_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            database, "DB_PATH", Path(directory) / "app.db"
        ):
            database.init_db()
            user = database.create_user("owner@example.com", "Owner", "hash")
            project = database.create_project_for_user(user["id"], "Workspace")
            dataset = database.create_dataset_for_user(user["id"], {
                "project_id": project["id"],
                "name": "Source data",
                "original_filename": "source.csv",
                "file_type": "csv",
                "source_path": "source.csv",
                "working_path": "working.csv",
                "row_count": 2,
                "column_count": 1,
                "profile": {"columns": []},
            })
            session = database.create_chat_session_for_user(
                user["id"], project["id"], dataset["id"], "Analysis"
            )
            database.create_chat_message_for_user(
                user["id"], project["id"], dataset["id"], "user", "hello", session_id=session["id"]
            )
            report = database.create_artifact(
                project["id"], "report", "Saved report", {"title": "Saved report"},
                dataset_id=dataset["id"], user_id=user["id"],
            )
            chart = database.create_artifact(
                project["id"], "chart", "Temporary chart", {},
                dataset_id=dataset["id"], user_id=user["id"],
            )

            deleted = database.delete_dataset_for_user(user["id"], project["id"], dataset["id"])

            self.assertIsNotNone(deleted)
            self.assertEqual(database.list_chat_sessions_for_user(user["id"], project["id"], dataset["id"]), [])
            artifacts = database.list_artifacts_for_user(user["id"], project["id"])
            self.assertEqual([artifact["id"] for artifact in artifacts], [report["id"]])
            self.assertIsNone(database.get_artifact_for_user(user["id"], project["id"], chart["id"]))
            self.assertEqual(artifacts[0]["dataset_id"], dataset["id"])


if __name__ == "__main__":
    unittest.main()
