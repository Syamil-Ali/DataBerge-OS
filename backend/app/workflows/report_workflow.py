from __future__ import annotations

import time
from typing import Any, Callable

from app.agents import AnalyticsTeam
from app.services.llm_observability import log_profile_run
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
    """Execute the report generation pipeline with template-driven building blocks.

    Steps:
        1. Data Readiness Assessment (Engineer)
        2. Data Investigation (Analyst)
        3. Narrative Generation (Reporter — template-driven blocks)
        4. Governance Review + Quality Pass
        5. Artifact Storage
    """
    from app.workflows.chat_workflow import _resolve_chat_dataset

    dataset, _, _ = _resolve_chat_dataset(
        project_id,
        payload.dataset_id,
        user_id=user_id,
    )

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

    start_ms = int(time.time() * 1000)

    # Step 1: Data Readiness Assessment (Engineer)
    _emit_progress(progress_callback, "readiness", "Assessing data readiness", 20)
    readiness_brief = team.data_engineer.assess_for_report(dataset)

    # Step 2: Data Investigation (Analyst)
    _emit_progress(progress_callback, "investigation", "Investigating patterns", 40)
    approved_plan = getattr(payload, "approved_plan", None)
    findings = team.data_analyst.investigate_for_report(
        dataset,
        readiness_brief,
        report_plan=approved_plan if isinstance(approved_plan, dict) else None,
    )

    # Step 3: Narrative Generation (Reporter — template-driven blocks)
    _emit_progress(progress_callback, "narrative", "Writing report narrative", 65)
    if _is_draft_brief_request(template, blocks):
        report = team.report.narrate(dataset, context, readiness_brief, findings)
        review_template = "executive"
    else:
        report = team.report.narrate_enhanced(
            dataset, context, readiness_brief, findings,
            template=template, blocks=blocks, block_definitions=custom_blocks or None,
        )
        review_template = template

    # Step 4: Governance Review + Quality Pass
    _emit_progress(progress_callback, "governance", "Running governance review", 85)
    report, review = team.governance.review_with_quality_pass(report, template=review_template)
    report = team.report.compose(report, template=template, block_definitions=custom_blocks or None)
    if isinstance(approved_plan, dict):
        report["approved_plan"] = approved_plan
    report["governance"] = review
    report = json_safe(report)

    # Step 5: Artifact Storage
    _emit_progress(progress_callback, "storage", "Saving draft artifact", 95)
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
    _emit_progress(progress_callback, "complete", "Draft ready for review", 100)

    # Log to MLflow
    elapsed_ms = int(time.time() * 1000) - start_ms
    try:
        from app.services.llm_observability import enabled
        if enabled():
            log_profile_run(
                dataset_id=payload.dataset_id,
                project_id=project_id,
                filename=str(dataset.get("name", "unknown")),
                file_type="report",
                row_count=int(dataset.get("row_count", 0)),
                column_count=int(dataset.get("column_count", 0)),
                profile={
                    "readiness_score": readiness_brief.get("readiness_score"),
                    "findings_count": len(findings),
                    "template": template,
                    "governance_warnings": review.get("warnings", []),
                },
                elapsed_ms=elapsed_ms,
            )
    except Exception:
        pass

    return json_safe(artifact)


def _is_draft_brief_request(template: str, blocks: Any) -> bool:
    return template == DRAFT_BRIEF_TEMPLATE
