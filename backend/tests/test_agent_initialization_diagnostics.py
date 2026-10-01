import unittest
from unittest.mock import patch

from app.agents import base


class AgentInitializationDiagnosticsTests(unittest.TestCase):
    def test_constructor_failure_is_logged_without_sensitive_exception_text(self):
        spec = base.AgentSpec("TestAgent", "test", "test")
        with patch.object(base, "Agent", object()), patch.object(
            base, "ObservableAgent", side_effect=ValueError("secret-password")
        ), patch.object(base, "build_model_config", return_value="test"):
            with self.assertLogs(base.logger, level="ERROR") as captured:
                self.assertIs(base.make_agno_agent(spec), spec)
        self.assertIn("ValueError", captured.output[0])
        self.assertNotIn("secret-password", captured.output[0])

    def test_missing_dependency_is_logged(self):
        spec = base.AgentSpec("TestAgent", "test", "test")
        with patch.object(base, "Agent", None):
            with self.assertLogs(base.logger, level="ERROR") as captured:
                self.assertIs(base.make_agno_agent(spec), spec)
        self.assertIn("dependency import failed", captured.output[0])
