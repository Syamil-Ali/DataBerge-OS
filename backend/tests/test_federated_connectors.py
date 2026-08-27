from __future__ import annotations

import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from app import settings
from app.connectors.contracts import ConnectorError, QueryResult, json_scalar
from app.connectors.postgres import validate_logical_select
from app.connectors.secrets import decrypt_connector_secret, encrypt_connector_secret
from app.services.federated import register_federated_dataset
from app.storage import database


class FakePostgresConnector:
    def inspect_table(self, config, secret, schema, table):
        return {
            "schema": schema,
            "table": table,
            "estimated_rows": 2_000_000,
            "columns": [
                {"name": "region", "data_type": "text", "native_type": "text"},
                {"name": "revenue", "data_type": "numeric", "native_type": "numeric"},
            ],
        }

    def preview(self, config, secret, schema, table, limit):
        return QueryResult(
            columns=[{"name": "region"}, {"name": "revenue"}],
            rows=[{"region": "North", "revenue": 20}, {"region": "South", "revenue": 30}],
            row_count=2,
            truncated=False,
            elapsed_ms=4,
        )


class FederatedConnectorTests(unittest.TestCase):
    def test_connector_values_use_one_json_safe_normalizer(self) -> None:
        self.assertEqual(json_scalar(Decimal("12.50")), 12.5)
        self.assertEqual(json_scalar(date(2026, 8, 27)), "2026-08-27")
        self.assertEqual(json_scalar(b"ok"), "6f6b")

    def test_connector_secrets_are_encrypted_and_round_trip(self) -> None:
        encrypted = encrypt_connector_secret({"password": "supabase-secret"})
        self.assertNotIn("supabase-secret", encrypted)
        self.assertEqual(decrypt_connector_secret(encrypted), {"password": "supabase-secret"})

    def test_federated_sql_is_restricted_to_active_dataset(self) -> None:
        self.assertEqual(
            validate_logical_select('select count(*) from "dataset"'),
            'select count(*) from "dataset"',
        )
        for unsafe in (
            "delete from dataset",
            "select * from private.users",
            "select * from dataset join users on true",
            "select * from dataset; select 1",
            "select * from dataset -- bypass",
            "select * from dataset union select current_user",
            "select * from dataset for update",
        ):
            with self.subTest(sql=unsafe), self.assertRaises(ConnectorError):
                validate_logical_select(unsafe)

    def test_registers_remote_table_without_materializing_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "app.db"
            with patch.object(database, "DB_PATH", db_path), patch.object(settings, "DB_PATH", db_path):
                database.init_db()
                user = database.create_user("remote@example.com", "Remote", "unused")
                project = database.create_project_for_user(user["id"], "Federated")
                connection = database.create_data_connection(
                    user["id"],
                    project["id"],
                    name="Supabase",
                    provider="supabase",
                    connector_type="postgresql",
                    config={
                        "host": "db.example.supabase.co",
                        "port": 5432,
                        "database": "postgres",
                        "username": "reader",
                        "sslmode": "require",
                    },
                    encrypted_secret=encrypt_connector_secret({"password": "secret"}),
                )
                with patch("app.services.federated.get_federated_connector", return_value=FakePostgresConnector()):
                    dataset = register_federated_dataset(
                        user["id"],
                        project["id"],
                        connection_id=connection["id"],
                        schema="public",
                        table="orders",
                    )

                self.assertEqual(dataset["status"], "federated")
                self.assertTrue(dataset["working_path"].startswith("federated://"))
                self.assertEqual(dataset["row_count"], 2_000_000)
                self.assertEqual(dataset["profile"]["source"]["access_mode"], "federated")
                source = database.get_dataset_source(user["id"], project["id"], dataset["id"])
                self.assertEqual(source["resource"], {"schema": "public", "table": "orders"})


if __name__ == "__main__":
    unittest.main()
