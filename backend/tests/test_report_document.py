from __future__ import annotations

import unittest

from data_berge_core.report_document import compose_report_document


class ReportDocumentTests(unittest.TestCase):
    def test_unwraps_schema_metadata_from_custom_content(self) -> None:
        result = compose_report_document({
            "title": "Risk brief",
            "template": "custom",
            "sections": [{
                "key": "risk_snapshot",
                "label": "Risk Snapshot",
                "content": {
                    "description": "Risk summary",
                    "type": "array",
                    "items": ["Risk increased by 12%.", "Two segments need review."],
                },
            }],
        })

        section = result["document"]["sections"][0]
        self.assertEqual(section["content"], ["Risk increased by 12%.", "Two segments need review."])
        self.assertEqual(section["presentation"]["kind"], "bullets")

    def test_sanitizes_model_selected_presentation_tokens(self) -> None:
        result = compose_report_document({
            "title": "Operations memo",
            "template": "custom",
            "sections": [{
                "key": "next_actions",
                "label": "Next Actions",
                "kind": "actions",
                "presentation": {
                    "variant": "untrusted-css-class",
                    "width": "200vw",
                    "emphasis": "primary",
                },
                "content": ["Assign an owner.", "Validate the affected segment."],
            }],
        })

        presentation = result["document"]["sections"][0]["presentation"]
        self.assertEqual(presentation["kind"], "actions")
        self.assertEqual(presentation["variant"], "standard")
        self.assertEqual(presentation["width"], "full")
        self.assertEqual(presentation["emphasis"], "primary")

    def test_builds_document_sections_for_legacy_reports(self) -> None:
        result = compose_report_document({
            "title": "Executive report",
            "template": "executive",
            "central_theme": "Retention is the primary risk.",
            "key_metrics": [{"name": "Retention", "value": "82%"}],
            "recommendations": ["Prioritize the at-risk segment."],
        })

        sections = result["document"]["sections"]
        self.assertEqual([section["key"] for section in sections], ["central_theme", "key_metrics", "recommendations"])
        self.assertEqual(result["document"]["theme"], "executive")
        self.assertEqual(result["document"]["version"], 2)


if __name__ == "__main__":
    unittest.main()
