from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services import llm_observability as observability


class FakeSpan:
    def __init__(self, owner, name: str, span_type: str, parent=None) -> None:
        self.owner = owner
        self.name = name
        self.span_type = span_type
        self.parent = parent
        self.inputs = None
        self.outputs = None
        self.attributes = {}

    def __enter__(self):
        self.owner.stack.append(self)
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.owner.stack.pop()

    def set_inputs(self, value) -> None:
        self.inputs = value

    def set_outputs(self, value) -> None:
        self.outputs = value

    def set_attribute(self, key, value) -> None:
        self.attributes[key] = value


class FakeMlflow:
    def __init__(self) -> None:
        self.stack = []
        self.spans = []
        self.trace_updates = []

    def start_span(self, name="span", span_type="UNKNOWN", attributes=None):
        span = FakeSpan(self, name, span_type, self.get_current_active_span())
        span.attributes.update(attributes or {})
        self.spans.append(span)
        return span

    def get_current_active_span(self):
        return self.stack[-1] if self.stack else None

    def update_current_trace(self, **kwargs) -> None:
        self.trace_updates.append(kwargs)

    def flush_trace_async_logging(self) -> None:
        return None


class ReportObservabilityTests(unittest.TestCase):
    def _patches(self, fake: FakeMlflow):
        return (
            patch.object(observability, "mlflow", fake),
            patch.object(observability, "enabled", return_value=True),
            patch.object(observability, "_configure"),
        )

    def test_report_operations_are_real_nested_spans_with_payloads(self) -> None:
        fake = FakeMlflow()
        p1, p2, p3 = self._patches(fake)
        with p1, p2, p3:
            with observability.report_trace(
                project_id="project-1",
                dataset={"id": "dataset-1", "name": "Population"},
                artifact_id="artifact-1",
                request={"template": "executive", "goal": "Explain the evidence"},
            ) as root:
                with observability.trace_span(
                    "report.investigation",
                    inputs={"decision": "investigate"},
                ) as investigation:
                    with observability.trace_span(
                        "investigation.query_1",
                        span_type="TOOL",
                        inputs={"sql": "SELECT 1"},
                    ) as query:
                        observability.set_span_outputs(query, {"decision": "accepted", "rows": [{"value": 1}]})
                observability.complete_report_trace(
                    root,
                    outputs={"title": "Evidence report", "status": "draft"},
                    metadata={"findings_count": 1},
                    usage_payload={"model": "test-model"},
                )

        root, investigation, query = fake.spans
        self.assertIs(investigation.parent, root)
        self.assertIs(query.parent, investigation)
        self.assertEqual(query.inputs["sql"], "SELECT 1")
        self.assertEqual(query.outputs["decision"], "accepted")
        self.assertEqual(fake.trace_updates[-1]["state"], "OK")

    def test_report_failure_records_error_on_root_trace(self) -> None:
        fake = FakeMlflow()
        p1, p2, p3 = self._patches(fake)
        with p1, p2, p3:
            with self.assertRaisesRegex(RuntimeError, "query failed"):
                with observability.report_trace(
                    project_id="project-1",
                    dataset={"id": "dataset-1", "name": "Population"},
                    artifact_id="artifact-1",
                    request={"template": "executive"},
                ):
                    raise RuntimeError("query failed")

        root = fake.spans[0]
        self.assertEqual(root.outputs["status"], "failed")
        self.assertEqual(root.outputs["error_type"], "RuntimeError")
        self.assertEqual(fake.trace_updates[-1]["state"], "ERROR")
        self.assertEqual(fake.trace_updates[-1]["tags"]["has_error"], "true")


if __name__ == "__main__":
    unittest.main()
