from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import settings
from app.api import datasets, relational
from app.main import app
from app.middleware.production import AuthRateLimiter
from app.services import files
from app.storage import database


class ApiSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.db_path = root / "app.db"
        self.upload_dir = root / "uploads"
        self.artifact_dir = root / "artifacts"
        self.upload_dir.mkdir()
        self.artifact_dir.mkdir()
        self.patches = [
            patch.object(database, "DB_PATH", self.db_path),
            patch.object(database, "UPLOAD_DIR", self.upload_dir),
            patch.object(database, "ARTIFACT_DIR", self.artifact_dir),
            patch.object(settings, "DB_PATH", self.db_path),
            patch.object(settings, "UPLOAD_DIR", self.upload_dir),
            patch.object(settings, "ARTIFACT_DIR", self.artifact_dir),
            patch.object(files, "UPLOAD_DIR", self.upload_dir),
            patch.object(datasets, "UPLOAD_DIR", self.upload_dir),
            patch.object(relational, "UPLOAD_DIR", self.upload_dir),
            patch("app.main.configure_agno_autolog"),
        ]
        for active_patch in self.patches:
            active_patch.start()
        database.init_db()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.temp.cleanup()

    def register(self, client: TestClient, email: str) -> str:
        response = client.post("/api/auth/register", json={
            "email": email,
            "name": "Test User",
            "password": "CorrectHorse42",
        })
        self.assertEqual(response.status_code, 201, response.text)
        self.assertNotIn("token", response.json())
        self.assertTrue(response.cookies.get(settings.AUTH_COOKIE_NAME))
        return str(response.json()["csrf_token"])

    def test_cookie_session_requires_csrf_for_mutations(self) -> None:
        csrf = self.register(self.client, "owner@example.com")
        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)

        blocked = self.client.post("/api/projects", json={"name": "Blocked"})
        self.assertEqual(blocked.status_code, 403)

        created = self.client.post(
            "/api/projects",
            json={"name": "Allowed"},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(created.status_code, 200, created.text)

    def test_users_cannot_read_another_users_project(self) -> None:
        owner_csrf = self.register(self.client, "owner@example.com")
        project = self.client.post(
            "/api/projects",
            json={"name": "Private"},
            headers={"X-CSRF-Token": owner_csrf},
        ).json()

        other_context = TestClient(app)
        other = other_context.__enter__()
        try:
            self.register(other, "other@example.com")
            response = other.get(f"/api/projects/{project['id']}/overview")
            self.assertEqual(response.status_code, 404)
        finally:
            other_context.__exit__(None, None, None)

    def test_authenticated_upload_updates_quota_and_profile(self) -> None:
        csrf = self.register(self.client, "upload@example.com")
        project = self.client.post(
            "/api/projects",
            json={"name": "Upload"},
            headers={"X-CSRF-Token": csrf},
        ).json()
        response = self.client.post(
            f"/api/projects/{project['id']}/datasets",
            files={"file": ("sample.csv", b"region,value\nNorth,10\nSouth,20\n", "text/csv")},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 200, response.text)
        dataset = response.json()
        profile = self.client.get(f"/api/projects/{project['id']}/datasets/{dataset['id']}/profile")
        self.assertEqual(profile.status_code, 200)
        self.assertGreater(database.get_user_storage(dataset["user_id"]), 0)

    def test_registration_rejects_weak_passwords(self) -> None:
        response = self.client.post("/api/auth/register", json={
            "email": "weak@example.com",
            "name": "Weak",
            "password": "short1",
        })
        self.assertEqual(response.status_code, 400)

    def test_production_configuration_fails_closed(self) -> None:
        with patch.object(settings, "IS_PRODUCTION", True), \
            patch.object(settings, "JWT_SECRET", "change-me-in-production-use-openssl-rand-hex-32"), \
            patch.object(settings, "COOKIE_SECURE", False), \
            patch.object(settings, "ALLOWED_HOSTS", ["*"]), \
            patch.dict("os.environ", {"CORS_ALLOW_ORIGINS": "*"}):
            with self.assertRaisesRegex(RuntimeError, "Unsafe runtime configuration"):
                settings.validate_runtime_config()

    def test_request_body_limit_rejects_before_parsing(self) -> None:
        response = self.client.post(
            "/api/auth/login",
            content=b"",
            headers={"Content-Length": str(settings.MAX_REQUEST_BODY_BYTES + 1)},
        )
        self.assertEqual(response.status_code, 413)

    def test_auth_rate_limiter_has_a_retry_window(self) -> None:
        limiter = AuthRateLimiter(limit=2, window_seconds=60)
        self.assertEqual(limiter.allow("client", now=10), (True, 0))
        self.assertEqual(limiter.allow("client", now=11), (True, 0))
        allowed, retry_after = limiter.allow("client", now=12)
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0)


if __name__ == "__main__":
    unittest.main()
