from __future__ import annotations

import time
from typing import Any, Callable

from app.agents import AnalyticsTeam
from app.services.llm_observability import (
    complete_report_trace,
    report_trace,
    set_span_outputs,
    stable_hash,
    trace_span,
)
from app.services.llm_usage import collect_llm_usage, merge_usage_payloads
from app.services.profiling import json_safe
from app.storage import database
from data_berge_core.skills.report_templates import get_template


ProgressCallback = Callable[[str, str, int], None]
DRAFT_BRIEF_TEMPLATE = "draft_brief"


def _emit_progress(callback: ProgressCallback | None, key: str, label: str, percent: int) -> None:
    if callback is None:
        return
    try:
        callback(key, label, percent)
    except Exception:
        return


def run_report_workflow(
    project_id: str,
    payload,
    user_id: str | None = None,
    artifact_id: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    """Execute and trace the full report generation decision and evidence pipeline."""
    from app.workflows.chat_workflow import _resolve_chat_dataset

    dataset, _, _ = _resolve_chat_dataset(project_id, payload.dataset_id, user_id=user_id)
    team = AnalyticsTeam(user_id=user_id)
    team.set_active_context(project_id, str(dataset.get("id") or payload.dataset_id))
    template = getattr(payload, "template", "executive") or "executive"
    template_definition = get_template(template)
    context = {
        "audience": payload.audience,
        "goal": payload.goal,
        "horizon": payload.horizon,
        "tone": payload.tone,
        "focus_areas": payload.focus_areas,
        "report_type": (
            getattr(payload, "report_type", None)
            or (template_definition or {}).get("name")
            or "Custom Report"
        ),
    }
    blocks = getattr(payload, "blocks", None)
    custom_blocks = [
        block.model_dump() if hasattr(block, "model_dump") else dict(block)
        for block in (getattr(payload, "custom_blocks", None) or [])
    ]
    approved_plan = getattr(payload, "approved_plan", None)
    start_ms = int(time.time() * 1000)
    stage_durations_ms: dict[str, int] = {}
    usage_events: list[dict[str, Any]] = []

    trace_request = {
        "project_id": project_id,
        "artifact_id": artifact_id,
        "dataset": {
            "id": dataset.get("id"),
            "name": dataset.get("name"),
            "row_count": dataset.get("row_count"),
            "column_count": dataset.get("column_count"),
            "profile": dataset.get("profile"),
        },
        "template": template,
        "report_type": context.get("report_type"),
        "context": context,
        "blocks": blocks,
        "custom_blocks": custom_blocks,
        "approved_plan": approved_plan,
    }

    with report_trace(
        project_id=project_id,
        dataset=dataset,
        artifact_id=str(artifact_id or "new-report"),
        request=trace_request,
        user_id=user_id,
    ) as root_span:
        _emit_progress(progress_callback, "readiness", "Assessing data readiness", 20)
        stage_started = time.perf_counter()
        with trace_span(
            "report.readiness_assessment",
            span_type="AGENT",
            inputs={
                "agent": "DataEngineerAgent",
                "skill": "EngineeringSkill",
                "dataset_profile": dataset.get("profile"),
                "report_goal": context.get("goal"),
            },
        ) as stage_span:
            with collect_llm_usage() as stage_usage:
                readiness_brief = team.data_engineer.assess_for_report(dataset)
            usage_events.extend(stage_usage)
            set_span_outputs(stage_span, {
                "decision": "proceed_to_investigation",
                "readiness_brief": readiness_brief,
                "llm_usage": merge_usage_payloads(*stage_usage),
            })
        stage_durations_ms["readiness"] = int((time.perf_counter() - stage_started) * 1000)

        _emit_progress(progress_callback, "investigation", "Investigating patterns", 40)
        stage_started = time.perf_counter()
        with trace_span(
            "report.investigation",
            span_type="AGENT",
            inputs={
                "agent": "DataAnalystAgent",
                "readiness_brief": readiness_brief,
                "approved_plan": approved_plan,
            },
        ) as stage_span:
            with collect_llm_usage() as stage_usage:
                findings = team.data_analyst.investigate_for_report(
                    dataset,
                    readiness_brief,
                    report_plan=approved_plan if isinstance(approved_plan, dict) else None,
                )
            usage_events.extend(stage_usage)
            set_span_outputs(stage_span, {
                "decision": "evidence_ready_for_narrative" if findings else "no_verified_findings",
                "finding_count": len(findings),
                "findings": findings,
                "llm_usage": merge_usage_payloads(*stage_usage),
            })
        stage_durations_ms["investigation"] = int((time.perf_counter() - stage_started) * 1000)

        _emit_progress(progress_callback, "narrative", "Writing report narrative", 65)
        stage_started = time.perf_counter()
        with trace_span(
            "report.narrative_generation",
            span_type="AGENT",
            inputs={
                "agent": "ReportAgent",
                "template": template,
                "blocks": blocks,
                "custom_blocks": custom_blocks,
                "audience_context": context,
                "readiness_brief": readiness_brief,
                "verified_findings": findings,
            },
        ) as stage_span:
            with collect_llm_usage() as stage_usage:
                if _is_draft_brief_request(template, blocks):
                    report = team.report.narrate(dataset, context, readiness_brief, findings)
                    review_template = "executive"
                    narrative_path = "draft_brief"
                else:
                    report = team.report.narrate_enhanced(
                        dataset,
                        context,
                        readiness_brief,
                        findings,
                        template=template,
                        blocks=blocks,
                        block_definitions=custom_blocks or None,
                    )
                    review_template = template
                    narrative_path = "template_driven"
            usage_events.extend(stage_usage)
            set_span_outputs(stage_span, {
                "decision": {
                    "path": narrative_path,
                    "generation_source": report.get("generation_source"),
                    "review_template": review_template,
                },
                "narrative": report,
                "llm_usage": merge_usage_payloads(*stage_usage),
            })
        stage_durations_ms["narrative"] = int((time.perf_counter() - stage_started) * 1000)

        _emit_progress(progress_callback, "governance", "Running governance review", 85)
        stage_started = time.perf_counter()
        pre_governance_hash = stable_hash(report)
        with trace_span(
            "report.governance_review",
            span_type="AGENT",
            inputs={
                "agent": "GovernanceAgent",
                "template": review_template,
                "narrative_hash": pre_governance_hash,
                "narrative": report,
            },
        ) as governance_span:
            with collect_llm_usage() as stage_usage:
                report, review = team.governance.review_with_quality_pass(report, template=review_template)
            usage_events.extend(stage_usage)
            set_span_outputs(governance_span, {
                "decision": {
                    "quality_pass_applied": review.get("quality_pass"),
                    "requires_approval": review.get("requires_approval"),
                    "passed_checks": review.get("passed"),
                    "total_checks": review.get("total"),
                    "report_changed": stable_hash(report) != pre_governance_hash,
                },
                "review": review,
                "refined_report": report,
                "llm_usage": merge_usage_payloads(*stage_usage),
            })

        with trace_span(
            "report.document_composition",
            span_type="CHAIN",
            inputs={
                "template": template,
                "block_definitions": custom_blocks,
                "governed_report": report,
            },
        ) as compose_span:
            report = team.report.compose(report, template=template, block_definitions=custom_blocks or None)
            set_span_outputs(compose_span, {
                "section_count": len(report.get("sections", []) or []),
                "document": report.get("document"),
            })
        stage_durations_ms["governance"] = int((time.perf_counter() - stage_started) * 1000)

        if isinstance(approved_plan, dict):
            report["approved_plan"] = approved_plan
        report["governance"] = review
        report = json_safe(report)

        _emit_progress(progress_callback, "storage", "Saving draft artifact", 95)
        stage_started = time.perf_counter()
        with trace_span(
            "report.artifact_storage",
            span_type="TOOL",
            inputs={
                "operation": "update" if artifact_id else "create",
                "artifact_id": artifact_id,
                "title": report.get("title"),
                "status": "draft",
                "report_hash": stable_hash(report),
            },
        ) as storage_span:
            if artifact_id:
                update = {
                    "status": "draft",
                    "title": str(report.get("title") or "Executive Report"),
                    "payload": report,
                }
                if user_id:
                    artifact = database.update_artifact_for_user(user_id, project_id, artifact_id, **update)
                else:
                    artifact = database.update_artifact(artifact_id, **update)
                if artifact is None:
                    raise FileNotFoundError("Report artifact not found for this project.")
            else:
                artifact = team.report.tools.create_report_artifact(project_id, payload.dataset_id, report)
            set_span_outputs(storage_span, {
                "artifact_id": artifact.get("id"),
                "title": artifact.get("title"),
                "status": artifact.get("status"),
                "dataset_id": artifact.get("dataset_id"),
            })
        stage_durations_ms["storage"] = int((time.perf_counter() - stage_started) * 1000)
        _emit_progress(progress_callback, "complete", "Draft ready for review", 100)

        elapsed_ms = int(time.time() * 1000) - start_ms
        document = report.get("document") if isinstance(report.get("document"), dict) else {}
        sections = document.get("sections") if isinstance(document.get("sections"), list) else report.get("sections", [])
        merged_usage = merge_usage_payloads(*usage_events)
        complete_report_trace(
            root_span,
            outputs={
                "artifact_id": artifact.get("id"),
                "title": artifact.get("title"),
                "status": artifact.get("status"),
                "report": report,
            },
            metadata={
                "elapsed_ms": elapsed_ms,
                "template": template,
                "report_type": context.get("report_type"),
                "artifact_id": artifact.get("id"),
                "generation_source": report.get("generation_source"),
                "findings_count": len(findings),
                "section_count": len(sections) if isinstance(sections, list) else 0,
                "governance_warning_count": len(review.get("warnings", []) or []),
                "readiness_score": readiness_brief.get("readiness_score"),
                "report_hash": stable_hash(report),
                "stage_durations_ms": json_safe(stage_durations_ms),
                "llm_calls": merged_usage.get("llm_calls"),
            },
            usage_payload=merged_usage,
        )
        return json_safe(artifact)


def _is_draft_brief_request(template: str, blocks: Any) -> bool:
    return template == DRAFT_BRIEF_TEMPLATE
