from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from data_berge_core.skills.governance import GovernanceSkill


CHART = {
    "title": "Population distribution",
    "type": "bar",
    "x": "bucket",
    "y": ["count"],
    "data": [{"bucket": "0-1000", "count": 7}],
}


def report_payload(content) -> dict:
    return {
        "title": "Population brief",
        "template": "custom",
        "generation_source": "llm",
        "sections": [{
            "key": "population_distribution",
            "label": "Population Distribution",
            "content": content,
            "presentation": {
                "kind": "chart",
                "variant": "standard",
                "width": "full",
                "emphasis": "supporting",
                "page_break_before": False,
            },
        }],
        "readiness": {"score": 10, "label": "Good", "limitations": ["Loaded sample only."]},
    }


class RefiningAgent:
    def run(self, prompt: str, stream: bool = False) -> SimpleNamespace:
        candidate = report_payload("Narrative text cannot render as a chart.")
        candidate.pop("generation_source")
        return SimpleNamespace(content=json.dumps({"refined": True, "payload": candidate}))


class GovernanceSkillTests(unittest.TestCase):
    def make_skill(self) -> GovernanceSkill:
        return GovernanceSkill.__new__(GovernanceSkill)

    def test_chart_section_requires_renderable_chart_data(self) -> None:
        governance = self.make_skill().review(
            report_payload("Narrative text cannot render as a chart."),
            template="custom",
        )

        self.assertLess(governance["passed"], governance["total"])
        self.assertIn("does not contain a renderable chart", governance["warnings"][0])

    def test_valid_chart_section_passes_content_check(self) -> None:
        governance = self.make_skill().review(report_payload([CHART]), template="custom")

        chart_check = next(
            check for check in governance["checks"]
            if check["check"] == "Population Distribution present"
        )
        self.assertTrue(chart_check["passed"])

    def test_quality_pass_cannot_replace_chart_or_drop_generation_metadata(self) -> None:
        skill = self.make_skill()
        skill.agent = RefiningAgent()
        original = report_payload([CHART])

        refined, governance = skill.review_with_quality_pass(original, template="custom")

        self.assertEqual(refined["sections"][0]["content"], [CHART])
        self.assertEqual(refined["generation_source"], "llm")
        self.assertFalse(governance["quality_pass"])
        self.assertIn("discarded", governance["quality_pass_warning"])


if __name__ == "__main__":
    unittest.main()
