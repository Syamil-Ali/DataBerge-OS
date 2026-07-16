from __future__ import annotations
from time import perf_counter
from typing import Any

from app.agents import AnalyticsTeam
from app.models.schemas import ReportRequest
from app.services.llm_observability import log_chat_run
from app.services.llm_usage import merge_usage_payloads, prompt_usage_payloads
from app.services.report_queue import queue_report_workflow
from app.storage import database
from data_berge_core.skills.report_templates import get_block_keys


def run_chat_workflow(
    project_id: str,
    dataset_id: str,
    message: str,
    session_id: str | None = None,
    user_id: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> dict:
    dataset, relational_schema, _ = _resolve_chat_dataset(project_id, dataset_id, user_id=user_id)
    team = AnalyticsTeam(user_id=user_id)
    team.set_active_context(project_id, str(dataset.get("id") or dataset_id))

    # Auto-create session if none provided
    if not session_id:
        if user_id:
            session = database.create_chat_session_for_user(user_id, project_id, dataset_id, _auto_title(message))
        else:
            session = database.create_chat_session(project_id, dataset_id, _auto_title(message))
        session_id = session["id"]
    else:
        # Update session title from first user message if still default
        session = (
            database.get_chat_session_for_user(user_id, project_id, session_id)
            if user_id
            else database.get_chat_session(session_id)
        )
        if not session:
            raise FileNotFoundError("Chat session not found for this project.")
        if str(session.get("dataset_id") or "") != str(dataset_id):
            raise FileNotFoundError("Chat session not found for this dataset.")
        if session and session["title"] == "New Chat":
            if user_id:
                database.update_chat_session_title_for_user(user_id, project_id, session_id, _auto_title(message))
            else:
                database.update_chat_session_title(session_id, _auto_title(message))

    agent_message = _message_with_attachments(message, attachments)
    user_payload = {"attachments": attachments} if attachments else None
    if user_id:
        all_history = database.list_chat_messages_for_user(
            user_id,
            project_id,
            dataset_id,
            session_id=session_id,
        )
        history = _history_with_report_state(all_history)
        database.create_chat_message_for_user(
            user_id,
            project_id,
            dataset_id,
            "user",
            message,
            payload=user_payload,
            session_id=session_id,
        )
    else:
        all_history = database.list_chat_messages(project_id, dataset_id, session_id=session_id)
        history = _history_with_report_state(all_history)
        database.create_chat_message(
            project_id,
            dataset_id,
            "user",
            message,
            payload=user_payload,
            session_id=session_id,
        )
    started = perf_counter()
    try:
        response = team.coordinator.respond(agent_message, dataset, history)
        response = _queue_report_execution(project_id, dataset_id, dataset, user_id, response)
    except Exception as exc:
        elapsed_ms = int((perf_counter() - started) * 1000)
        log_chat_run(
            project_id=project_id,
            dataset=dataset,
            message=agent_message,
            history=history,
            response={"answer": "", "evidence": [], "data": [], "chart": None, "sql": None, "confidence": 0},
            elapsed_ms=elapsed_ms,
            error=str(exc),
            session_id=session_id,
            user_id=user_id,
        )
        raise
    elapsed_ms = int((perf_counter() - started) * 1000)
    prompt_info = response.pop("_prompt_info", None)
    token_usage = response.pop("_token_usage", None)
    manager_usage = response.pop("_manager_token_usage", None)
    combined_usage = merge_usage_payloads(
        manager_usage,
        token_usage,
        *prompt_usage_payloads(prompt_info),
    )
    if combined_usage:
        prompt_info = prompt_info or {}
        prompt_info["token_usage"] = combined_usage
    if user_id:
        assistant_message = database.create_chat_message_for_user(
            user_id,
            project_id,
            dataset_id,
            "assistant",
            response["answer"],
            response,
            session_id=session_id,
        )
    else:
        assistant_message = database.create_chat_message(project_id, dataset_id, "assistant", response["answer"], response, session_id=session_id)
    response["chat_message_id"] = assistant_message["id"]
    response["session_id"] = session_id
    if response.get("chart"):
        team.data_analyst.tools.create_chart_artifact(
            project_id,
            dataset_id,
            response["chart"].get("title", "Generated chart"),
            response["chart"],
            response.get("data", []),
            message,
        )
    log_chat_run(
        project_id=project_id,
        dataset=dataset,
        message=agent_message,
        history=history,
        response=response,
        elapsed_ms=elapsed_ms,
        prompt_info=prompt_info,
        session_id=session_id,
        user_id=user_id,
    )
    return response


def _message_with_attachments(message: str, attachments: list[dict[str, Any]] | None) -> str:
    contexts = [
        str(attachment.get("context") or "").strip()
        for attachment in attachments or []
        if str(attachment.get("context") or "").strip()
    ]
    return "\n\n".join([*contexts, message.strip()]) if contexts else message


def _queue_report_execution(
    project_id: str,
    dataset_id: str,
    dataset: dict[str, Any],
    user_id: str | None,
    response: dict[str, Any],
) -> dict[str, Any]:
    report_request = response.get("report_request") if isinstance(response.get("report_request"), dict) else {}
    if not user_id or response.get("active_skill") != "reporting" or response.get("action") != "execute_requested":
        return response

    template = str(report_request.get("template") or "executive")
    blocks = report_request.get("blocks")
    payload = ReportRequest(
        dataset_id=dataset_id,
        audience=str(report_request.get("audience") or "Leadership team"),
        goal=str(report_request.get("goal") or f"Identify risks, opportunities, and next actions for {dataset.get('name') or 'the dataset'}"),
        horizon=str(report_request.get("horizon") or "Next quarter"),
        tone=str(report_request.get("tone") or "Strategic"),
        focus_areas=report_request.get("focus_areas") if isinstance(report_request.get("focus_areas"), list) else ["growth", "risk", "quality"],
        template=template,
        report_type=str(report_request.get("report_type") or "") or None,
        blocks=blocks if isinstance(blocks, list) else get_block_keys(template) or None,
        custom_blocks=report_request.get("custom_blocks") if isinstance(report_request.get("custom_blocks"), list) else None,
        approved_plan=report_request.get("approved_plan") if isinstance(report_request.get("approved_plan"), dict) else None,
    )
    artifact = queue_report_workflow(project_id, payload, user_id=user_id)
    template_label = {
        "quick_brief": "Quick Brief",
        "technical": "Technical Report",
        "research": "Research Report",
    }.get(template, str(report_request.get("report_type") or "Report"))
    return {
        "answer": (
            f"The {template_label} is now generating from the approved draft. "
            "Please go to the Executive Report page to watch the progress."
        ),
        "evidence": [
            f"Queued {template_label} generation after the user executed the draft.",
            "The Executive Report page will show the normal loading progress.",
        ],
        "sql": None,
        "data": [],
        "chart": None,
        "confidence": 0.95,
        "mode": "report_generation_queued",
        "active_skill": "reporting",
        "handled_by": "report_agent",
        "lead_agent": "report_agent",
        "artifact": artifact,
        "action": "queued",
        "shared_state": {
            **(response.get("shared_state") if isinstance(response.get("shared_state"), dict) else {}),
            "active_lead": "report_agent",
            "user_intent": "report",
            "conversation_focus": "executive_report",
        },
    }


def build_chat_profile_context(project_id: str, dataset_id: str, user_id: str | None = None) -> dict[str, Any]:
    """Return the resolved profile context used by Explorer/chat for debugging."""
    dataset, relational_schema, source = _resolve_chat_dataset(project_id, dataset_id, user_id=user_id)
    profile = dataset.get("profile", {}) or {}
    return {
        "project_id": project_id,
        "dataset_id": dataset_id,
        "context_source": source,
        "explanation": (
            "This export is the resolved backend context for Explorer. "
            "MLflow/chat observability intentionally logs a small request summary, "
            "while this payload includes the full profile object used by the app."
        ),
        "observability_request_summary_shape": {
            "question": "<user message>",
            "dataset": {
                "id": dataset.get("id"),
                "name": dataset.get("name"),
                "row_count": dataset.get("row_count"),
                "column_count": dataset.get("column_count"),
            },
            "history": "<last chat messages>",
        },
        "resolved_dataset": dataset,
        "resolved_profile": profile,
        "relational_schema": relational_schema,
    }


def _resolve_chat_dataset(
    project_id: str,
    dataset_id: str,
    user_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None, str]:
    dataset = database.get_dataset(dataset_id)
    relational_schema = None

    if dataset and dataset["project_id"] == project_id:
        if user_id and dataset.get("user_id") != user_id:
            raise FileNotFoundError("Dataset not found for this project.")
        relational_schema = database.get_relational_schema(dataset_id)
        if relational_schema and relational_schema["project_id"] == project_id and (
            not user_id or relational_schema.get("user_id") == user_id
        ):
            return _with_relational_context(dataset, relational_schema), relational_schema, "dataset_with_linked_relational_schema"
        return dataset, None, "dataset"

    relational_schema = database.get_relational_schema(dataset_id)
    if relational_schema and relational_schema["project_id"] == project_id:
        if user_id and relational_schema.get("user_id") != user_id:
            raise FileNotFoundError("Dataset not found for this project.")
        materialized = _try_materialize_schema_dataset(project_id, relational_schema)
        if materialized:
            return _with_relational_context(materialized, relational_schema), relational_schema, "materialized_relational_schema_dataset"
        return _schema_to_virtual_dataset(relational_schema), relational_schema, "relational_schema_virtual_dataset"

    raise FileNotFoundError("Dataset not found for this project.")


def _try_materialize_schema_dataset(project_id: str, schema_record: dict[str, Any]) -> dict[str, Any] | None:
    """Ensure a Data Model has the generic working dataset used by SQL tools."""
    schema_id = str(schema_record.get("id") or "")
    if not schema_id:
        return None

    dataset = database.get_dataset(schema_id)
    if dataset and dataset.get("project_id") == project_id:
        return dataset

    user_id = str(schema_record.get("user_id") or "")
    if not user_id:
        return None

    try:
        from app.api.relational import _materialize_schema_dataset

        _materialize_schema_dataset(project_id, schema_id, schema_record, user_id)
    except Exception:
        return None
    return database.get_dataset(schema_id)


def _auto_title(message: str) -> str:
    """Generate a short session title from the first user message."""
    clean = message.strip().replace("\n", " ")
    if len(clean) > 50:
        clean = clean[:47] + "..."
    return clean or "New Chat"


def _history_with_report_state(
    messages: list[dict[str, Any]],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Keep recent chat context plus the latest actionable report plan."""
    recent = [_history_message_with_attachments(item) for item in messages[-limit:]]
    report_state = next(
        (
            item
            for item in reversed(messages)
            if str(item.get("role")) == "assistant"
            and isinstance(item.get("payload"), dict)
            and (
                isinstance(item["payload"].get("report_plan"), dict)
                or isinstance(item["payload"].get("report_draft"), dict)
                or item["payload"].get("action") in {"queued", "saved"}
            )
        ),
        None,
    )
    if report_state is not None and report_state not in recent:
        recent.insert(0, report_state)
    return recent


def _history_message_with_attachments(message: dict[str, Any]) -> dict[str, Any]:
    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
    attachments = payload.get("attachments") if isinstance(payload.get("attachments"), list) else []
    if not attachments:
        return message
    contexts = [
        str(attachment.get("context") or "").strip()
        for attachment in attachments
        if isinstance(attachment, dict) and str(attachment.get("context") or "").strip()
    ]
    if not contexts:
        return message
    return {
        **message,
        "content": "\n\n".join([*contexts, str(message.get("content") or "")]),
    }


def _schema_to_virtual_dataset(schema_record: dict[str, Any]) -> dict[str, Any]:
    """Build a virtual dataset dict from a relational schema so chat/report can work."""
    schema = schema_record.get("schema", {}) or {}
    tables = schema.get("tables", {}) or {}
    total_rows = sum(t.get("row_count", 0) for t in tables.values())
    total_columns = sum(t.get("column_count", 0) for t in tables.values())

    # Use the first table's profile as the primary profile (unified format)
    first_table_profile = next(iter(tables.values()), None) or {}
    profile = {
        "tables": tables,
        "relationships": schema.get("relationships", []),
        "description_map": schema.get("description_map", {}),
        "relational_schema": _schema_chat_context(schema_record),
    }

    return {
        "id": schema_record.get("id"),
        "project_id": schema_record.get("project_id"),
        "name": schema_record.get("name"),
        "original_filename": schema_record.get("original_filename", ""),
        "file_type": "xlsx",
        "source_path": schema_record.get("source_path", ""),
        "working_path": "",
        "row_count": total_rows,
        "column_count": total_columns,
        "status": schema_record.get("status", "confirmed"),
        "created_at": schema_record.get("created_at", ""),
        "updated_at": schema_record.get("updated_at", ""),
        "profile": profile,
    }


def _with_relational_context(dataset: dict[str, Any], schema_record: dict[str, Any]) -> dict[str, Any]:
    """Attach confirmed Data Model metadata to the dataset context used by chat."""
    enriched = dict(dataset)
    profile = dict(enriched.get("profile") or {})
    profile["relational_schema"] = _schema_chat_context(schema_record)
    enriched["profile"] = profile
    return enriched


def _schema_chat_context(schema_record: dict[str, Any]) -> dict[str, Any]:
    schema = schema_record.get("schema", {}) or {}
    tables = schema.get("tables", {}) or {}
    relationships = [
        relationship
        for relationship in schema.get("relationships", []) or []
        if relationship.get("active") is not False
    ]
    table_summaries = []
    for name, table in tables.items():
        columns = table.get("columns", []) or []
        described_columns = [
            {
                "name": column.get("name"),
                "description": column.get("description"),
            }
            for column in columns[:8]
            if column.get("name") and column.get("description")
        ]
        table_summaries.append(
            {
                "name": name,
                "row_count": table.get("row_count", 0),
                "column_count": table.get("column_count", len(columns)),
                "columns": [column.get("name") for column in columns[:12] if column.get("name")],
                "described_columns": described_columns,
            }
        )

    source_context = _schema_source_context(schema_record)
    return {
        "schema_id": schema_record.get("id"),
        "name": schema_record.get("name"),
        "status": schema_record.get("status"),
        "source": source_context,
        "table_count": len(tables),
        "table_names": list(tables.keys()),
        "relationship_count": len(relationships),
        "tables": table_summaries,
        "relationships": [
            {
                "from_table": relationship.get("from_table"),
                "from_column": relationship.get("from_column"),
                "to_table": relationship.get("to_table"),
                "to_column": relationship.get("to_column"),
                "cardinality": relationship.get("cardinality"),
                "confidence": relationship.get("confidence"),
            }
            for relationship in relationships
        ],
        "analysis_dataset_note": "Explorer and chat SQL run on the confirmed model working dataset. Multi-table columns are prefixed as Table__Column.",
    }


def _schema_source_context(schema_record: dict[str, Any]) -> dict[str, Any]:
    schema = schema_record.get("schema", {}) or {}
    tables = schema.get("tables", {}) or {}
    source: dict[str, Any] = {}
    for table in tables.values():
        candidate = table.get("source") or {}
        if candidate:
            source = candidate
            break

    if not source:
        return {}

    context = {
        "source_type": source.get("source_type"),
        "dataset_id": source.get("opendosm_dataset_id"),
        "title": source.get("opendosm_title") or source.get("original_name"),
        "description": source.get("opendosm_description"),
        "frequency": source.get("opendosm_frequency"),
        "data_source": source.get("opendosm_data_source"),
        "data_as_of": source.get("opendosm_data_as_of"),
        "last_updated": source.get("opendosm_last_updated"),
        "sample_limit": source.get("sample_limit"),
        "tables": source.get("opendosm_tables") or [],
    }

    if context.get("source_type") == "opendosm" and context.get("dataset_id") and not context.get("description"):
        try:
            from app.services import opendosm

            metadata = opendosm.fetch_metadata(str(context["dataset_id"]))
            context.update({
                "title": metadata.get("title") or context.get("title"),
                "description": metadata.get("description") or context.get("description"),
                "frequency": metadata.get("frequency") or context.get("frequency"),
                "data_source": metadata.get("data_source") or context.get("data_source"),
                "data_as_of": metadata.get("data_as_of") or context.get("data_as_of"),
                "last_updated": metadata.get("last_updated") or context.get("last_updated"),
            })
        except Exception:
            pass

    return {key: value for key, value in context.items() if value not in (None, "", [])}
