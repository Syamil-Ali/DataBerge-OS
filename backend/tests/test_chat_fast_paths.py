from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from app.agents.base import normalize_base_url, sanitize_openai_compatible_tools
from app.agents.coordinator import AgentAssignment, ManagerDecision, TeamCoordinator
from app.workflows.chat_workflow import _history_with_report_state
from data_berge_core.skills.query import QuerySkill
from pydantic import ValidationError


def sample_dataset() -> dict:
    columns = [
        {"name": "age"},
        {"name": "sex"},
        {"name": "date"},
        {"name": "ethnicity"},
        {"name": "population"},
    ]
    return {
        "id": "dataset-1",
        "project_id": "project-1",
        "name": "Population - Malaysia",
        "row_count": 10,
        "column_count": 5,
        "profile": {"row_count": 10, "column_count": 5, "columns": columns},
    }


class FakeMemory:
    def get_context_summary(self, dataset_name: str | None) -> str:
        return ""

    def record_analysis(self, **kwargs) -> None:
        return None

    def record_pattern(self, *args) -> None:
        return None


class FakeManager:
    def __init__(self, decision: ManagerDecision) -> None:
        self.decision = decision

    def run(self, prompt: str, stream: bool = False) -> SimpleNamespace:
        return SimpleNamespace(content=self.decision)


class FakeAnalyst:
    skill_names = ["intake", "profiling", "query", "visualization", "reporting"]

    def __init__(self, query: QuerySkill) -> None:
        self.query = query

    def answer(self, message: str, dataset: dict, *args, assigned_skill=None, **kwargs) -> dict:
        response = self.query._answer_dataset_shape_question(message, dataset)
        assert response is not None
        response["active_skill"] = assigned_skill or "query"
        return response

    def _select_skill(self, message: str, dataset: dict, history: list) -> str:
        return "query"


class FakeEngineer:
    def should_lead(self, *args, **kwargs) -> bool:
        return False


class FakeReporter:
    pass


def coordinator_with(decision: ManagerDecision, query: QuerySkill) -> TeamCoordinator:
    coordinator = TeamCoordinator.__new__(TeamCoordinator)
    coordinator.data_analyst = FakeAnalyst(query)
    coordinator.data_engineer = FakeEngineer()
    coordinator.report_agent = FakeReporter()
    coordinator.memory = FakeMemory()
    coordinator.manager_agent = FakeManager(decision)
    return coordinator


class AgenticCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.query = QuerySkill.__new__(QuerySkill)
        self.dataset = sample_dataset()

    def test_field_count_is_answered_by_the_assigned_query_tool(self) -> None:
        decision = ManagerDecision(
            action="delegate",
            intent="dataset_shape",
            focus="field_count",
            assignments=[
                AgentAssignment(
                    agent="data_analyst",
                    task="How many fields are in the dataset?",
                    skill="query",
                )
            ],
            rationale="A dataset fact requires the Analyst's query tool.",
        )
        response = coordinator_with(decision, self.query).respond(
            "How many fields are in the dataset?", self.dataset, []
        )

        self.assertEqual(
            response["answer"],
            "Population - Malaysia has 5 fields: age, sex, date, ethnicity, and population.",
        )
        self.assertEqual(response["lead_agent"], "data_analyst")
        self.assertEqual(response["orchestration"]["action"], "delegate")
        self.assertNotIn("iterations", response)
        self.assertNotIn("reflections", response)

    def test_manager_handles_conversation_without_a_role_assignment(self) -> None:
        decision = ManagerDecision(
            action="respond",
            response="Hey. What would you like to explore?",
            intent="conversation",
            focus="greeting",
            rationale="No dataset work is required.",
        )
        response = coordinator_with(decision, self.query).respond("hey", self.dataset, [])

        self.assertEqual(response["answer"], "Hey. What would you like to explore?")
        self.assertEqual(response["lead_agent"], "team_manager")
        self.assertEqual(response["orchestration"]["assignments"], [])

    def test_manager_decision_can_be_parsed_from_json(self) -> None:
        coordinator = TeamCoordinator.__new__(TeamCoordinator)
        content = json.dumps({
            "action": "delegate",
            "intent": "analysis",
            "focus": "count",
            "assignments": [
                {"agent": "data_analyst", "task": "Count the rows", "skill": "query"}
            ],
            "rationale": "Requires a dataset tool.",
            "confidence": 0.9,
        })

        decision = coordinator._parse_decision(content)

        self.assertIsNotNone(decision)
        self.assertEqual(decision.assignments[0].agent, "data_analyst")

    def test_reflection_loop_is_not_part_of_the_coordinator(self) -> None:
        self.assertFalse(hasattr(TeamCoordinator, "_needs_reflection"))
        self.assertFalse(hasattr(TeamCoordinator, "_respond_with_loop"))

    def test_assignment_schema_rejects_a_skill_owned_by_another_agent(self) -> None:
        with self.assertRaises(ValidationError):
            AgentAssignment(
                agent="data_engineer",
                task="Count the dataset fields",
                skill="query",
            )

    def test_shape_tool_still_has_a_deterministic_accuracy_path(self) -> None:
        self.assertTrue(
            self.query.can_answer_without_model("How many fields are in the dataset?", self.dataset)
        )
        response = self.query._answer_dataset_shape_question("How many rows are there?", self.dataset)
        self.assertEqual(response["answer"], "Population - Malaysia has 10 rows.")

    def test_google_base_url_uses_openai_compatibility_path(self) -> None:
        self.assertEqual(
            normalize_base_url("https://generativelanguage.googleapis.com/v1beta"),
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        )

    def test_openai_compatible_tools_exclude_agno_runtime_metadata(self) -> None:
        raw_tools = [{
            "type": "function",
            "function": {
                "name": "get_dataset_profile",
                "description": "Get the profile.",
                "parameters": {"type": "object", "properties": {}},
                "requires_confirmation": False,
                "external_execution": False,
                "approval_type": "none",
            },
        }]

        sanitized = sanitize_openai_compatible_tools(raw_tools)

        self.assertEqual(
            set(sanitized[0]["function"]),
            {"name", "description", "parameters"},
        )
        self.assertIn("requires_confirmation", raw_tools[0]["function"])

    def test_recent_history_keeps_an_older_actionable_report_plan(self) -> None:
        plan_message = {
            "role": "assistant",
            "content": "Review this report plan.",
            "payload": {"action": "plan", "report_plan": {"sections": [{"key": "scope"}]}},
        }
        messages = [plan_message] + [
            {"role": "user", "content": f"Follow-up {index}", "payload": {}}
            for index in range(14)
        ]

        history = _history_with_report_state(messages, limit=10)

        self.assertIs(history[0], plan_message)
        self.assertEqual(len(history), 11)
        self.assertEqual(
            normalize_base_url("https://generativelanguage.googleapis.com/v1beta/openai/"),
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        )


if __name__ == "__main__":
    unittest.main()
