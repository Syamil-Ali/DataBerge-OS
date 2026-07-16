from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any


TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "reasoning_tokens",
)

_USAGE_EVENTS: ContextVar[list[dict[str, Any]] | None] = ContextVar("llm_usage_events", default=None)


@contextmanager
def collect_llm_usage():
    events: list[dict[str, Any]] = []
    token = _USAGE_EVENTS.set(events)
    try:
        yield events
    finally:
        _USAGE_EVENTS.reset(token)


def record_run_usage(run_output: Any) -> dict[str, Any]:
    payload = extract_run_usage(run_output)
    events = _USAGE_EVENTS.get()
    if payload and events is not None:
        events.append(payload)
    return payload


def extract_run_usage(run_output: Any) -> dict[str, Any]:
    metrics = getattr(run_output, "metrics", None)
    if not metrics:
        return {}

    def metric_value(*names: str) -> int | float | None:
        for name in names:
            value = getattr(metrics, name, None)
            if value is None and isinstance(metrics, dict):
                value = metrics.get(name)
            if isinstance(value, list):
                numeric = [item for item in value if isinstance(item, (int, float))]
                if numeric:
                    return sum(numeric)
            elif isinstance(value, (int, float)):
                return value
        return None

    input_tokens = metric_value("input_tokens")
    output_tokens = metric_value("output_tokens")
    total_tokens = metric_value("total_tokens")
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    usage: dict[str, int] = {}
    for key, value in (
        ("input_tokens", input_tokens),
        ("output_tokens", output_tokens),
        ("total_tokens", total_tokens),
        ("cache_read_input_tokens", metric_value("cache_read_tokens")),
        ("cache_creation_input_tokens", metric_value("cache_write_tokens")),
        ("reasoning_tokens", metric_value("reasoning_tokens")),
    ):
        if value is not None:
            usage[key] = int(value)

    payload: dict[str, Any] = {}
    if usage:
        payload["usage"] = usage
    cost = metric_value("cost")
    if cost is not None:
        payload["cost"] = {"total_cost": float(cost)}
    if model := getattr(run_output, "model", None):
        payload["model"] = str(model)
    if provider := getattr(run_output, "model_provider", None):
        payload["provider"] = str(provider)
    if payload:
        payload["llm_calls"] = 1
    return payload


def merge_usage_payloads(*payloads: dict[str, Any] | None) -> dict[str, Any]:
    valid = [payload for payload in payloads if isinstance(payload, dict) and payload]
    if not valid:
        return {}

    usage: dict[str, int] = {}
    total_cost = 0.0
    has_cost = False
    models: list[str] = []
    providers: list[str] = []
    llm_calls = 0

    for payload in valid:
        raw_usage = payload.get("usage")
        if isinstance(raw_usage, dict):
            for key in TOKEN_FIELDS:
                value = raw_usage.get(key)
                if isinstance(value, (int, float)):
                    usage[key] = usage.get(key, 0) + int(value)
        raw_cost = payload.get("cost")
        if isinstance(raw_cost, dict):
            value = raw_cost.get("total_cost")
            if isinstance(value, (int, float)):
                total_cost += float(value)
                has_cost = True
        model = payload.get("model")
        if model and str(model) not in models:
            models.append(str(model))
        provider = payload.get("provider")
        if provider and str(provider) not in providers:
            providers.append(str(provider))
        calls = payload.get("llm_calls")
        llm_calls += int(calls) if isinstance(calls, (int, float)) else 1

    merged: dict[str, Any] = {"llm_calls": llm_calls}
    if usage:
        merged["usage"] = usage
    if has_cost:
        merged["cost"] = {"total_cost": total_cost}
    if models:
        merged["model"] = models[0] if len(models) == 1 else ",".join(models)
        merged["models"] = models
    if providers:
        merged["provider"] = providers[0] if len(providers) == 1 else ",".join(providers)
        merged["providers"] = providers
    return merged


def prompt_usage_payloads(prompt_info: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(prompt_info, dict):
        return []
    payloads: list[dict[str, Any]] = []
    usage = prompt_info.get("token_usage")
    if isinstance(usage, dict) and usage:
        payloads.append(usage)
    payloads.extend(prompt_usage_payloads(prompt_info.get("upstream")))
    return payloads
