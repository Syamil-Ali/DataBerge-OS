from __future__ import annotations

import hashlib
import hmac
import json
import socket
import time
from contextlib import contextmanager
from typing import Any, Iterator
from urllib.parse import urlparse

from app import settings
from data_berge_core.contracts import get_flat_profile

try:
    import mlflow
    from mlflow.tracing.constant import SpanAttributeKey, TraceMetadataKey
except Exception:  # pragma: no cover - observability must never break app runtime
    mlflow = None  # type: ignore[assignment]
    TraceMetadataKey = None  # type: ignore[assignment]
    SpanAttributeKey = None  # type: ignore[assignment]


_AGNO_AUTOLOG_CONFIGURED = False
_TRACKING_CHECKED_AT = 0.0
_TRACKING_REACHABLE = False


def enabled() -> bool:
    return bool(settings.MLFLOW_TRACKING_ENABLED and mlflow is not None and _tracking_uri_reachable())


def _tracking_uri_reachable() -> bool:
    global _TRACKING_CHECKED_AT, _TRACKING_REACHABLE

    uri = settings.MLFLOW_TRACKING_URI
    parsed = urlparse(uri)
    if parsed.scheme not in {"http", "https"}:
        return True

    now = time.monotonic()
    if now - _TRACKING_CHECKED_AT < 2:
        return _TRACKING_REACHABLE

    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=0.25):
            _TRACKING_REACHABLE = True
    except OSError:
        _TRACKING_REACHABLE = False
    _TRACKING_CHECKED_AT = now
    return _TRACKING_REACHABLE


def now_ms() -> int:
    return int(time.time() * 1000)


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def pseudonymous_user_hash(user_id: str | None) -> str | None:
    secret = settings.OBSERVABILITY_ID_SECRET
    if not user_id or not secret:
        return None
    return hmac.new(
        secret.encode("utf-8"),
        str(user_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]


def json_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, default=str))


def _safe_log_params(params: dict[str, Any]) -> None:
    if not enabled():
        return
    try:
        for key, value in params.items():
            if value is None:
                continue
            text = str(value)
            mlflow.log_param(key, text[:500])
    except Exception:
        return


def _safe_log_metrics(metrics: dict[str, int | float | bool | None]) -> None:
    if not enabled():
        return
    try:
        for key, value in metrics.items():
            if value is None:
                continue
            mlflow.log_metric(key, float(value))
    except Exception:
        return


def _safe_log_dict(payload: dict[str, Any], artifact_file: str) -> None:
    if not enabled():
        return
    try:
        mlflow.log_dict(payload, artifact_file)
    except Exception:
        return


def _configure() -> None:
    if not enabled():
        return
    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)


def configure_agno_autolog() -> None:
    global _AGNO_AUTOLOG_CONFIGURED
    if _AGNO_AUTOLOG_CONFIGURED or not enabled():
        return
    try:
        _configure()
        import mlflow.agno

        mlflow.agno.autolog(log_traces=True, silent=True)
        _AGNO_AUTOLOG_CONFIGURED = True
    except Exception:
        return


def _trace_payload(value: Any, max_chars: int = 250_000) -> Any:
    """Keep trace payloads inspectable while bounding pathological profile/report sizes."""
    try:
        encoded = json.dumps(value, ensure_ascii=False, default=str, allow_nan=False)
    except (TypeError, ValueError):
        encoded = json.dumps(value, ensure_ascii=False, default=str)
    if len(encoded) <= max_chars:
        return json.loads(encoded)
    return {
        "truncated": True,
        "original_json_chars": len(encoded),
        "preview": encoded[:max_chars],
        "payload_hash": stable_hash(value),
    }


def has_active_trace() -> bool:
    if mlflow is None:
        return False
    try:
        return mlflow.get_current_active_span() is not None
    except Exception:
        return False


@contextmanager
def trace_span(
    name: str,
    *,
    span_type: str = "CHAIN",
    inputs: Any | None = None,
    attributes: dict[str, Any] | None = None,
    require_active_trace: bool = True,
) -> Iterator[Any | None]:
    """Create a real nested MLflow span without ever blocking application execution."""
    if not enabled() or (require_active_trace and not has_active_trace()):
        yield None
        return
    try:
        _configure()
        manager = mlflow.start_span(name=name, span_type=span_type, attributes=attributes)
    except Exception:
        yield None
        return
    with manager as span:
        if inputs is not None:
            span.set_inputs(_trace_payload(inputs))
        yield span


@contextmanager
def report_trace(
    *,
    project_id: str,
    dataset: dict[str, Any],
    artifact_id: str,
    request: dict[str, Any],
    user_id: str | None = None,
) -> Iterator[Any | None]:
    """Root trace for the live report workflow; child operations nest below it."""
    if not enabled():
        yield None
        return
    try:
        _configure()
        manager = mlflow.start_span(
            name="Data-Berge report generation",
            span_type="CHAIN",
            attributes={
                "data_berge.workflow": "report_generation",
                "data_berge.artifact_id": artifact_id,
            },
        )
    except Exception:
        yield None
        return

    user_hash = pseudonymous_user_hash(user_id)
    tags = {
        "data_berge.kind": "report",
        "project_id": project_id,
        "dataset_id": str(dataset.get("id") or ""),
        "dataset_name": str(dataset.get("name") or ""),
        "artifact_id": artifact_id,
        "has_error": "false",
    }
    if user_hash:
        tags["data_berge.user_hash"] = user_hash

    with manager as span:
        span.set_inputs(_trace_payload(request))
        try:
            mlflow.update_current_trace(
                tags=tags,
                metadata={
                    "artifact_id": artifact_id,
                    "dataset_id": str(dataset.get("id") or ""),
                    "template": str(request.get("template") or ""),
                    "report_type": str(request.get("report_type") or ""),
                },
                request_preview=f"{request.get('report_type') or request.get('template')} for {dataset.get('name')}",
                state="IN_PROGRESS",
                session_id=artifact_id,
            )
        except Exception:
            pass
        try:
            yield span
        except Exception as exc:
            set_span_outputs(span, {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
            try:
                mlflow.update_current_trace(
                    tags={**tags, "has_error": "true"},
                    metadata={"error_type": type(exc).__name__},
                    response_preview=str(exc)[:500],
                    state="ERROR",
                )
            except Exception:
                pass
            raise
        finally:
            if hasattr(mlflow, "flush_trace_async_logging"):
                try:
                    mlflow.flush_trace_async_logging()
                except Exception:
                    pass


def set_span_outputs(span: Any | None, outputs: Any) -> None:
    if span is None:
        return
    try:
        span.set_outputs(_trace_payload(outputs))
    except Exception:
        return


def set_span_attributes(span: Any | None, attributes: dict[str, Any]) -> None:
    if span is None:
        return
    try:
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, _trace_payload(value, max_chars=20_000))
    except Exception:
        return


def complete_report_trace(
    span: Any | None,
    *,
    outputs: dict[str, Any],
    metadata: dict[str, Any],
    usage_payload: dict[str, Any] | None = None,
) -> None:
    set_span_outputs(span, outputs)
    if span is None or mlflow is None:
        return
    usage_payload = usage_payload or {}
    token_usage = usage_payload.get("usage") if isinstance(usage_payload, dict) else None
    model_name = str(usage_payload.get("model") or settings.AGNO_MODEL)
    if SpanAttributeKey is not None:
        try:
            if token_usage:
                span.set_attribute(SpanAttributeKey.CHAT_USAGE, token_usage)
            span.set_attribute(SpanAttributeKey.MODEL, model_name)
        except Exception:
            pass
    trace_metadata = {key: str(value)[:1000] for key, value in metadata.items() if value is not None}
    if token_usage and TraceMetadataKey is not None:
        trace_metadata[TraceMetadataKey.TOKEN_USAGE] = json.dumps(token_usage)
        trace_metadata[TraceMetadataKey.MODEL_ID] = model_name
    cost = usage_payload.get("cost") if isinstance(usage_payload, dict) else None
    if cost and TraceMetadataKey is not None:
        trace_metadata[TraceMetadataKey.COST] = json.dumps(cost)
    try:
        mlflow.update_current_trace(
            metadata=trace_metadata,
            response_preview=str(outputs.get("title") or "Report draft generated")[:500],
            state="OK",
            model_id=model_name,
        )
    except Exception:
        return


@contextmanager
def mlflow_run(run_name: str, tags: dict[str, Any] | None = None) -> Iterator[dict[str, int]]:
    state = {"start_ms": now_ms()}
    if not enabled():
        yield state
        return
    try:
        _configure()
        with mlflow.start_run(run_name=run_name):
            if tags:
                mlflow.set_tags({key: str(value)[:500] for key, value in tags.items() if value is not None})
            yield state
    except Exception:
        yield state


def log_profile_run(
    *,
    dataset_id: str,
    project_id: str,
    filename: str,
    file_type: str,
    row_count: int,
    column_count: int,
    profile: dict[str, Any],
    elapsed_ms: int,
    user_id: str | None = None,
) -> None:
    user_hash = pseudonymous_user_hash(user_id)
    with mlflow_run(
        "data-profile",
        tags={
            "data_berge.kind": "profile",
            "dataset_id": dataset_id,
            "project_id": project_id,
            "filename": filename,
            "data_berge.user_hash": user_hash,
        },
    ):
        metadata = profile.get("metadata", {})
        _safe_log_params(
            {
                "file_type": file_type,
                "profile_hash": stable_hash(profile),
                "numeric_columns": ",".join(metadata.get("numeric_columns", []) or [])[:500],
                "categorical_columns": ",".join(metadata.get("categorical_columns", []) or [])[:500],
                "text_columns": ",".join(metadata.get("text_columns", []) or [])[:500],
            }
        )
        _safe_log_metrics(
            {
                "row_count": row_count,
                "column_count": column_count,
                "missing_cells": metadata.get("missing_cells", 0),
                "duplicate_rows": metadata.get("duplicate_rows", 0),
                "profile_json_size": json_size(profile),
                "elapsed_ms": elapsed_ms,
                "has_bivariate_analysis": bool(profile.get("bivariate_analysis")),
            }
        )
        _safe_log_dict(
            {
                "quality_flags": profile.get("quality_flags", []),
                "top_correlations": (profile.get("correlations", []) or [])[:10],
                "metadata": metadata,
            },
            "profile_summary.json",
        )
        _safe_log_dict(profile, "profile.json")


def log_chat_run(
    *,
    project_id: str,
    dataset: dict[str, Any],
    message: str,
    history: list[dict[str, Any]],
    response: dict[str, Any],
    elapsed_ms: int,
    prompt_info: dict[str, Any] | None = None,
    error: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
) -> None:
    prompt_info = prompt_info or {}
    mode = response.get("mode") or infer_mode(response)
    if not enabled():
        return
    try:
        _configure()
        sql = response.get("sql")
        chart = response.get("chart")
        prompt_template = prompt_info.get("template")
        rendered_prompt = prompt_info.get("rendered_prompt")
        usage_payload = prompt_info.get("token_usage") or response.get("_token_usage") or {}
        prompt_payload = _prompt_audit_payload(prompt_info)
        orchestration = response.get("orchestration") if isinstance(response.get("orchestration"), dict) else {}
        manager_fallback = orchestration.get("fallback") if isinstance(orchestration.get("fallback"), dict) else None

        request_payload: dict[str, Any] = {
            "question": message,
            "dataset": {
                "id": dataset.get("id"),
                "name": dataset.get("name"),
                "row_count": dataset.get("row_count"),
                "column_count": dataset.get("column_count"),
            },
            "history": [
                {"role": item.get("role"), "content": str(item.get("content", ""))[:700]}
                for item in history[-8:]
            ],
        }
        request_payload["resolved_profile_context"] = _chat_profile_context(dataset)
        profile_context = prompt_info.get("profile_context_json")
        if profile_context:
            request_payload["prompt_profile_context"] = profile_context
        response_payload = {
            "answer": response.get("answer"),
            "mode": mode,
            "confidence": response.get("confidence"),
            "lead_agent": response.get("lead_agent") or response.get("handled_by"),
            "active_skill": response.get("active_skill"),
            "shared_state": response.get("shared_state"),
            "orchestration": response.get("orchestration"),
            "handoff": response.get("handoff"),
            "sql": sql,
            "chart": chart,
            "data_preview": (response.get("data") or [])[:10],
            "evidence": response.get("evidence", []),
            "error": error,
        }
        execution_trace = _execution_trace(response, mode, history, sql, chart, prompt_payload)
        intermediate_outputs = {
            "agent_decision": {
                "mode": mode,
                "lead_agent": response.get("lead_agent") or response.get("handled_by"),
                "active_skill": response.get("active_skill"),
                "used_sql": bool(sql),
                "used_chart": bool(chart),
                "data_rows": len(response.get("data") or []),
                "history_messages": len(history),
                "orchestration": response.get("orchestration"),
            },
            "execution_trace": execution_trace,
            "prompt": prompt_payload,
        }
        trace_metadata = {
            "elapsed_ms": str(elapsed_ms),
            "answer_length": str(len(str(response.get("answer", "")))),
            "question_hash": stable_hash(message),
            "profile_context_hash": stable_hash(request_payload.get("resolved_profile_context")),
            "profile_json_size": str(json_size(dataset.get("profile", {}) or {})),
            "prompt_template_hash": stable_hash(prompt_template) if prompt_template else "",
            "rendered_prompt_hash": stable_hash(rendered_prompt) if rendered_prompt else "",
            "sql_hash": stable_hash(sql) if sql else "",
            "chart_type": chart.get("type") if isinstance(chart, dict) else "",
            "model": settings.AGNO_MODEL,
            "base_url_set": str(bool(settings.AGNO_BASE_URL)).lower(),
            "lead_agent": str(response.get("lead_agent") or response.get("handled_by") or ""),
            "active_skill": str(response.get("active_skill") or ""),
            "handoff": str(bool(response.get("handoff"))).lower(),
            "assignment_count": str(len((response.get("orchestration") or {}).get("assignments", []) or [])),
            "manager_fallback_used": str(bool(manager_fallback)).lower(),
        }
        if manager_fallback:
            trace_metadata.update({
                "manager_failure_stage": str(manager_fallback.get("stage") or "unknown"),
                "manager_error_type": str(manager_fallback.get("error_type") or "UnknownManagerError"),
            })
        relational_schema = (dataset.get("profile", {}) or {}).get("relational_schema", {})
        if isinstance(relational_schema, dict) and relational_schema:
            trace_metadata.update({
                "relational_table_count": str(relational_schema.get("table_count", "")),
                "relational_relationship_count": str(relational_schema.get("relationship_count", "")),
            })
        token_usage = usage_payload.get("usage") if isinstance(usage_payload, dict) else None
        cost = usage_payload.get("cost") if isinstance(usage_payload, dict) else None
        model_name = str(usage_payload.get("model") or settings.AGNO_MODEL)
        model_provider = str(usage_payload.get("provider") or "")
        llm_calls = usage_payload.get("llm_calls")
        trace_metadata["model"] = model_name
        if model_provider:
            trace_metadata["model_provider"] = model_provider
        if isinstance(llm_calls, (int, float)):
            trace_metadata["llm_calls"] = str(int(llm_calls))
        if token_usage:
            trace_metadata.update({
                "input_tokens": str(token_usage.get("input_tokens", "")),
                "output_tokens": str(token_usage.get("output_tokens", "")),
                "total_tokens": str(token_usage.get("total_tokens", "")),
            })
            if TraceMetadataKey is not None:
                trace_metadata[TraceMetadataKey.TOKEN_USAGE] = json.dumps(token_usage)
                trace_metadata[TraceMetadataKey.MODEL_ID] = model_name
        if cost and TraceMetadataKey is not None:
            trace_metadata[TraceMetadataKey.COST] = json.dumps(cost)
        if isinstance(cost, dict) and isinstance(cost.get("total_cost"), (int, float)):
            trace_metadata["total_cost"] = str(float(cost["total_cost"]))
        trace_tags = {
            "data_berge.kind": "chat",
            "project_id": project_id,
            "dataset_id": str(dataset.get("id")),
            "dataset_name": str(dataset.get("name")),
            "agent_mode": mode,
            "lead_agent": str(response.get("lead_agent") or response.get("handled_by") or ""),
            "active_skill": str(response.get("active_skill") or ""),
            "has_error": str(bool(error)).lower(),
            "has_agent_error": str(bool(manager_fallback)).lower(),
        }
        user_hash = pseudonymous_user_hash(user_id)
        if user_hash:
            trace_tags["data_berge.user_hash"] = user_hash

        @mlflow.trace(name="Data-Berge chat turn", span_type="AGENT")
        def _record_chat_trace(request: dict[str, Any], intermediate: dict[str, Any]) -> dict[str, Any]:
            mlflow.update_current_trace(
                tags=trace_tags,
                metadata=trace_metadata,
                request_preview=message[:500],
                response_preview=str(response.get("answer", ""))[:500],
                state="ERROR" if error else "OK",
                session_id=session_id or str(dataset.get("id")),
            )
            # Set span-level attributes for MLflow cost calculation and token display
            if SpanAttributeKey is not None:
                try:
                    span = mlflow.get_current_active_span()
                    if span is not None:
                        if token_usage:
                            span.set_attribute(SpanAttributeKey.CHAT_USAGE, token_usage)
                        if model_name:
                            span.set_attribute(SpanAttributeKey.MODEL, model_name)
                except Exception:
                    pass
            if manager_fallback:
                try:
                    with mlflow.start_span(name="agent.team_manager.error", span_type="AGENT") as failure_span:
                        failure_span.set_inputs({
                            "agent": "team_manager",
                            "model": settings.AGNO_MODEL,
                            "stage": manager_fallback.get("stage"),
                        })
                        failure_span.set_attribute("error.type", str(
                            manager_fallback.get("error_type") or "UnknownManagerError"
                        ))
                        failure_span.set_attribute("error.handled", True)
                        failure_span.set_outputs({
                            "status": "fallback_handled",
                            "fallback_action": orchestration.get("action"),
                            "fallback_lead_agent": response.get("lead_agent") or response.get("handled_by"),
                            "assignments": orchestration.get("assignments") or [],
                        })
                        failure_span.set_status("ERROR")
                except Exception:
                    pass
            return {**response_payload, "intermediate_outputs": intermediate}

        _record_chat_trace(request_payload, intermediate_outputs)
        if hasattr(mlflow, "flush_trace_async_logging"):
            mlflow.flush_trace_async_logging()
    except Exception:
        return


def _chat_profile_context(dataset: dict[str, Any]) -> dict[str, Any]:
    profile = dataset.get("profile", {}) or {}
    flat = get_flat_profile(profile)
    relational_schema = profile.get("relational_schema")
    context: dict[str, Any] = {
        "dataset_id": dataset.get("id"),
        "dataset_name": dataset.get("name"),
        "working_dataset": {
            "row_count": dataset.get("row_count"),
            "column_count": dataset.get("column_count"),
        },
        "flat_profile_summary": {
            "row_count": flat.get("row_count"),
            "column_count": flat.get("column_count"),
            "numeric_columns": (flat.get("metadata", {}) or {}).get("numeric_columns", []),
            "categorical_columns": (flat.get("metadata", {}) or {}).get("categorical_columns", []),
            "text_columns": (flat.get("metadata", {}) or {}).get("text_columns", []),
            "quality_flags": flat.get("quality_flags", []),
            "columns": [
                {
                    "name": column.get("name"),
                    "semantic_type": column.get("semantic_type"),
                    "description": column.get("description"),
                    "engineering_role": column.get("engineering_role"),
                }
                for column in (flat.get("columns", []) or [])[:80]
            ],
        },
    }
    if isinstance(relational_schema, dict) and relational_schema:
        context["relational_schema"] = relational_schema
        context["interpretation_note"] = (
            "For multi-table uploads, working_dataset row/column counts describe the joined analysis table. "
            "The relational_schema block is the model-level context for table count, table names, and relationships."
        )

    profile_size = json_size(profile)
    context["profile_json_size"] = profile_size
    if profile_size <= 300_000:
        context["full_profile"] = profile
    else:
        context["full_profile"] = {
            "omitted": True,
            "reason": "Profile is larger than 300000 JSON characters; use the Explorer Export profile button for full context.",
        }
    return context


def _prompt_audit_payload(prompt_info: dict[str, Any]) -> dict[str, Any]:
    prompt_info = prompt_info or {}
    prompt_template = prompt_info.get("template")
    rendered_prompt = prompt_info.get("rendered_prompt")
    payload: dict[str, Any] = {
        "name": prompt_info.get("name"),
        "version": prompt_info.get("version") or settings.MLFLOW_PROMPT_VERSION,
        "source": prompt_info.get("source"),
        "uri": prompt_info.get("uri"),
        "template_hash": stable_hash(prompt_template) if prompt_template else None,
        "rendered_hash": stable_hash(rendered_prompt) if rendered_prompt else None,
        "template_size": json_size(prompt_template) if prompt_template else 0,
        "rendered_size": json_size(rendered_prompt) if rendered_prompt else 0,
        "rendered_logged": settings.MLFLOW_LOG_PROMPT_INSTANCES,
    }
    if "profile_context_json" in prompt_info:
        payload["profile_context"] = prompt_info.get("profile_context_json")
    if "token_usage" in prompt_info:
        payload["token_usage"] = prompt_info.get("token_usage")
    if prompt_template:
        payload["template"] = prompt_template
    if rendered_prompt:
        text = str(rendered_prompt)
        payload["rendered_prompt_preview"] = text[:5000]
        if settings.MLFLOW_LOG_PROMPT_INSTANCES:
            payload["rendered_prompt"] = rendered_prompt
    if prompt_info.get("upstream"):
        payload["upstream"] = _prompt_audit_payload(prompt_info.get("upstream") or {})
    return payload


def _execution_trace(
    response: dict[str, Any],
    mode: str,
    history: list[dict[str, Any]],
    sql: Any,
    chart: Any,
    prompt_payload: dict[str, Any],
) -> dict[str, Any]:
    shared_state = response.get("shared_state") or {}
    orchestration = response.get("orchestration") or {}
    assignments = orchestration.get("assignments") or []
    manager_fallback = orchestration.get("fallback") if isinstance(orchestration.get("fallback"), dict) else None
    handoff = response.get("handoff")

    steps: list[dict[str, Any]] = [
        {
            "stage": "coordinator",
            "mode": shared_state.get("agentic_mode") or mode,
            "lead_agent": response.get("lead_agent") or response.get("handled_by") or shared_state.get("active_lead"),
            "previous_lead": shared_state.get("previous_lead"),
            "handoff_reason": shared_state.get("handoff_reason"),
            "user_intent": shared_state.get("user_intent"),
            "conversation_focus": shared_state.get("conversation_focus"),
            "tool_count": shared_state.get("tool_count"),
            "plan_steps": shared_state.get("plan_steps"),
            "manager": orchestration.get("manager"),
            "action": orchestration.get("action"),
            "assignments": assignments,
        },
        {
            "stage": "agent",
            "lead_agent": response.get("lead_agent") or response.get("handled_by"),
            "active_skill": response.get("active_skill"),
            "response_mode": mode,
            "confidence": response.get("confidence"),
        },
    ]
    if manager_fallback:
        steps.append({
            "stage": "agent_error",
            "agent": "team_manager",
            "model": settings.AGNO_MODEL,
            "failure_stage": manager_fallback.get("stage"),
            "error_type": manager_fallback.get("error_type"),
            "handled_by_fallback": True,
        })
    if handoff:
        steps.append({"stage": "handoff", **handoff})
    if sql:
        steps.append({"stage": "sql_execution", "sql": sql, "data_rows": len(response.get("data") or [])})
    if chart:
        steps.append({"stage": "chart_generation", "chart_type": chart.get("type") if isinstance(chart, dict) else None})
    if prompt_payload.get("name") or prompt_payload.get("rendered_hash"):
        steps.append({
            "stage": "llm_prompt",
            "name": prompt_payload.get("name"),
            "version": prompt_payload.get("version"),
            "source": prompt_payload.get("source"),
            "rendered_hash": prompt_payload.get("rendered_hash"),
            "rendered_size": prompt_payload.get("rendered_size"),
            "has_upstream_prompt": bool(prompt_payload.get("upstream")),
        })

    return {
        "summary": {
            "mode": mode,
            "lead_agent": response.get("lead_agent") or response.get("handled_by"),
            "active_skill": response.get("active_skill"),
            "history_messages": len(history),
            "used_sql": bool(sql),
            "used_chart": bool(chart),
            "handoff": bool(handoff),
            "manager_action": orchestration.get("action"),
            "assignment_count": len(assignments),
            "manager_fallback_used": bool(manager_fallback),
        },
        "steps": steps,
    }


def infer_mode(response: dict[str, Any]) -> str:
    if response.get("sql"):
        return "sql"
    evidence = " ".join(str(item).lower() for item in response.get("evidence", []))
    answer = str(response.get("answer", "")).lower()
    if "clarification" in evidence or "clarify" in answer:
        return "clarify"
    if "profile" in evidence:
        return "profile"
    return "unknown"
