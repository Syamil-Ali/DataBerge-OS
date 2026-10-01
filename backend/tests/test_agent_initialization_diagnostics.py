import unittest
from unittest.mock import patch

from app.agents import base


class AgentInitializationDiagnosticsTests(unittest.TestCase):
    def test_google_compatible_agent_constructs_with_deployed_configuration(self):
        # This must use the real adapter: mocks would hide a missing SDK in CI.
        with patch.multiple(
            base,
            AGNO_MODEL="gemini-3.1-flash-lite",
            AGNO_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/",
            AGNO_API_KEY="test-not-a-real-key",
        ):
            self.assertIsNotNone(base.CompatibleOpenAILike)
            model = base.build_model_config({"temperature": 0.0})
            self.assertEqual(model.id, "gemini-3.1-flash-lite")
            self.assertEqual(model.base_url, "https://generativelanguage.googleapis.com/v1beta/openai/")
            agent = base.make_agno_agent(base.AgentSpec("TestAgent", "test", "test"))
            self.assertTrue(callable(getattr(agent, "run", None)))

    def test_missing_compatible_adapter_does_not_use_native_model_parser(self):
        with patch.multiple(base, AGNO_BASE_URL="https://example.test/v1/", CompatibleOpenAILike=None):
            with self.assertRaises(ImportError):
                base.build_model_config()

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
