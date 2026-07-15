from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.workflows.chat_workflow import _queue_report_execution
from data_berge_core.skills.reporting import ReportingSkill


DATASET = {
    "id": "dataset-1",
    "project_id": "project-1",
    "name": "Population",
    "row_count": 10,
    "column_count": 2,
    "profile": {
        "row_count": 10,
        "column_count": 2,
        "columns": [
            {"name": "date", "semantic_type": "date", "missing_pct": 0},
            {"name": "population", "semantic_type": "numeric", "missing_pct": 0},
        ],
        "metadata": {"numeric_columns": ["population"]},
    },
}

CONTEXT = {
    "audience": "Policy stakeholders",
    "goal": "Create a concise population brief",
    "horizon": "Current",
    "tone": "Strategic",
    "focus_areas": ["planning"],
    "template": "custom",
    "blocks": [],
}


class FailingAgent:
    def run(self, prompt: str, stream: bool = False) -> None:
        raise RuntimeError("provider rejected the request")


class JsonAgent:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def run(self, prompt: str, stream: bool = False) -> SimpleNamespace:
        self.prompts.append(prompt)
        return SimpleNamespace(content=json.dumps({
            "title": "Population Planning Snapshot",
            "report_type": "Quick Brief",
            "audience": "Policy stakeholders",
            "goal": "Support planning",
            "horizon": "Current",
            "tone": "Strategic",
            "focus_areas": ["planning"],
            "sections": [{
                "key": "planning_signal",
                "label": "Planning Signal",
                "purpose": "Define which population evidence should guide planning.",
                "kind": "narrative",
                "data_fields": ["date", "population", "invented_field"],
                "chart_intent": None,
                "required": True,
            }],
        }))


class FakeTools:
    def draft_report_payload(self, *args, **kwargs) -> dict:
        return {
            "title": "Deterministic report",
            "executive_summary": "Starter summary",
            "key_findings": ["10 sample rows are available."],
        }

    def starter_charts(self, columns: list[dict]) -> list[dict]:
        charts = []
        for column in columns:
            if column.get("name") == "population":
                charts.append({
                    "title": "Distribution of population",
                    "type": "bar",
                    "x": "bucket",
                    "y": ["count"],
                    "data": [{"bucket": "0-1000", "count": 7}],
                })
        return charts


class ReportingSkillTests(unittest.TestCase):
    def make_skill(self, agent) -> ReportingSkill:
        skill = ReportingSkill.__new__(ReportingSkill)
        skill.agent = agent
        skill.tools = FakeTools()
        skill._last_draft_error = None
        return skill

    def test_custom_plan_fails_closed_when_the_provider_fails(self) -> None:
        plan = self.make_skill(FailingAgent()).plan(DATASET, CONTEXT, "Create a brief")

        self.assertEqual(plan["generation_source"], "failed")
        self.assertEqual(plan["sections"], [])
        self.assertIn("provider rejected", plan["generation_warning"])

    def test_llm_plan_contains_structure_without_report_content(self) -> None:
        plan = self.make_skill(JsonAgent()).plan(DATASET, CONTEXT, "Create a brief")

        self.assertEqual(plan["generation_source"], "llm")
        self.assertEqual(plan["template"], "custom")
        self.assertEqual(plan["sections"][0]["label"], "Planning Signal")
        self.assertEqual(plan["sections"][0]["data_fields"], ["date", "population"])
        self.assertNotIn("content", plan["sections"][0])

    def test_revision_preserves_plan_identity_and_increments_version(self) -> None:
        agent = JsonAgent()
        skill = self.make_skill(agent)
        first = skill.answer(DATASET, "Create a custom brief", [])
        history = [{"role": "assistant", "payload": first}]

        revised = skill.answer(DATASET, "Revise the report plan: rename the first section", history)

        self.assertEqual(revised["action"], "plan_revised")
        self.assertEqual(revised["report_plan"]["version"], 2)
        self.assertEqual(revised["report_plan"]["plan_id"], first["report_plan"]["plan_id"])
        self.assertIn("Previous report plan JSON", agent.prompts[-1])

    def test_confirmation_freezes_the_plan_for_generation(self) -> None:
        skill = self.make_skill(JsonAgent())
        first = skill.answer(DATASET, "Create a custom brief", [])
        history = [{"role": "assistant", "payload": first}]

        confirmed = skill.answer(
            DATASET,
            "Confirm the revised report plan and generate the report",
            history,
        )

        request = confirmed["report_request"]
        self.assertEqual(confirmed["action"], "execute_requested")
        self.assertEqual(request["approved_plan"]["status"], "approved")
        self.assertEqual(request["blocks"], ["planning_signal"])
        self.assertEqual(request["custom_blocks"][0]["data_fields"], ["date", "population"])

    def test_a_queued_plan_cannot_be_confirmed_twice(self) -> None:
        skill = self.make_skill(JsonAgent())
        first = skill.answer(DATASET, "Create a custom brief", [])
        history = [
            {"role": "assistant", "payload": first},
            {"role": "assistant", "payload": {"action": "queued"}},
        ]

        response = skill.answer(
            DATASET,
            "Confirm this report plan and generate the report",
            history,
        )

        self.assertNotEqual(response["action"], "execute_requested")

    def test_custom_content_schema_follows_the_approved_section_kind(self) -> None:
        skill = self.make_skill(JsonAgent())

        schemas = skill._build_block_schemas_from_definitions(
            "custom",
            [{
                "key": "population_metrics",
                "label": "Population Metrics",
                "description": "Show grounded population measures.",
                "kind": "metrics",
            }],
        )

        self.assertEqual(schemas["population_metrics"]["type"], "array")
        self.assertEqual(schemas["population_metrics"]["items"]["type"], "object")
        self.assertIn("value", schemas["population_metrics"]["items"]["properties"])

    def test_verified_chart_replaces_model_prose_in_an_approved_chart_block(self) -> None:
        skill = self.make_skill(JsonAgent())
        dataset = {
            **DATASET,
            "profile": {
                **DATASET["profile"],
                "columns": [
                    DATASET["profile"]["columns"][0],
                    {
                        **DATASET["profile"]["columns"][1],
                        "histogram": {"bins": [0, 1000], "counts": [7]},
                    },
                ],
            },
        }
        blocks = [{
            "key": "population_distribution",
            "label": "Population Distribution",
            "description": "Show the loaded population distribution.",
            "kind": "chart",
            "data_fields": ["population"],
            "required": True,
        }]

        report = skill._enrich_enhanced_narrative(
            {"title": "Population brief", "population_distribution": "The distribution is skewed."},
            dataset,
            CONTEXT,
            {"readiness_score": 10, "readiness_label": "Good", "data_limitations": []},
            [{
                "finding": "Total population in the loaded rows.",
                "columns_used": ["population"],
                "chart": {
                    "title": "Population total",
                    "type": "table",
                    "columns": ["total_population"],
                    "data": [{"total_population": 20179.5}],
                },
            }],
            template="custom",
            block_definitions=blocks,
        )

        chart_content = report["population_distribution"]
        self.assertIsInstance(chart_content, list)
        self.assertEqual(len(chart_content), 1)
        self.assertEqual(chart_content[0]["title"], "Distribution of population")
        self.assertNotEqual(chart_content, "The distribution is skewed.")

    def test_report_prompt_carries_authoritative_field_semantics(self) -> None:
        skill = self.make_skill(JsonAgent())
        dataset = {
            **DATASET,
            "profile": {
                **DATASET["profile"],
                "columns": [
                    {
                        **DATASET["profile"]["columns"][0],
                        "description": "[Date] Annual data with MM-DD fixed at 01-01.",
                        "sample_values": ["1970-01-01"],
                    },
                    DATASET["profile"]["columns"][1],
                ],
            },
        }

        prompt = skill._enhanced_narration_prompt(
            dataset,
            CONTEXT,
            {"readiness_score": 10, "readiness_label": "Good", "data_limitations": []},
            [],
            template="custom",
            block_definitions=[{
                "key": "scope",
                "label": "Scope",
                "description": "Explain scope.",
                "kind": "callout",
            }],
        )

        self.assertIn("Annual data with MM-DD fixed at 01-01", prompt)
        self.assertIn("Do not describe a valid source date as stale", prompt)

    def test_confirmed_plan_survives_chat_queue_validation(self) -> None:
        skill = self.make_skill(JsonAgent())
        first = skill.answer(DATASET, "Create a custom brief", [])
        confirmed = skill.answer(
            DATASET,
            "Confirm this report plan and generate the report",
            [{"role": "assistant", "payload": first}],
        )

        with patch(
            "app.workflows.chat_workflow.queue_report_workflow",
            return_value={"id": "artifact-1", "status": "generating"},
        ) as queue:
            queued = _queue_report_execution(
                DATASET["project_id"],
                DATASET["id"],
                DATASET,
                "user-1",
                {**confirmed, "active_skill": "reporting"},
            )

        payload = queue.call_args.args[1]
        self.assertEqual(queued["action"], "queued")
        self.assertEqual(payload.approved_plan["status"], "approved")
        self.assertEqual(payload.custom_blocks[0].data_fields, ["date", "population"])


if __name__ == "__main__":
    unittest.main()
