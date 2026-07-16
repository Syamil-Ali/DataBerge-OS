from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.settings import (
    AGNO_API_KEY,
    AGNO_BASE_URL,
    AGNO_MAX_RETRIES,
    AGNO_MODEL,
    AGNO_REQUEST_TIMEOUT_SECONDS,
)
from app.services.llm_usage import record_run_usage
from app.services.llm_observability import set_span_attributes, set_span_outputs, trace_span

try:
    from agno.agent import Agent
except Exception:  # pragma: no cover - lets the app run before dependencies are installed
    Agent = None  # type: ignore[assignment]

try:
    from agno.models.openai.like import OpenAILike
except Exception:  # pragma: no cover
    OpenAILike = None  # type: ignore[assignment]


AGNO_INTERNAL_TOOL_FIELDS = {
    "requires_confirmation",
    "external_execution",
    "approval_type",
}


def sanitize_openai_compatible_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove Agno runtime metadata that is not part of the OpenAI tool schema."""
    sanitized: list[dict[str, Any]] = []
    for tool in tools:
        clean_tool = dict(tool)
        function = tool.get("function")
        if isinstance(function, dict):
            clean_tool["function"] = {
                key: value
                for key, value in function.items()
                if key not in AGNO_INTERNAL_TOOL_FIELDS
            }
        sanitized.append(clean_tool)
    return sanitized


if OpenAILike is not None:
    class CompatibleOpenAILike(OpenAILike):
        """OpenAI-compatible model that emits provider-standard function schemas."""

        def get_request_params(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            params = super().get_request_params(*args, **kwargs)
            tools = params.get("tools")
            if isinstance(tools, list):
                params["tools"] = sanitize_openai_compatible_tools(tools)
            return params
else:  # pragma: no cover
    CompatibleOpenAILike = None  # type: ignore[assignment,misc]


if Agent is not None:
    class ObservableAgent(Agent):
        def run(self, *args: Any, **kwargs: Any) -> Any:
            agent_name = str(getattr(self, "name", None) or self.__class__.__name__)
            prompt = args[0] if args else kwargs.get("input") or kwargs.get("message")
            with trace_span(
                f"llm.{agent_name}",
                span_type="LLM",
                inputs={
                    "agent": agent_name,
                    "prompt": prompt,
                    "stream": kwargs.get("stream", False),
                },
            ) as span:
                run_output = super().run(*args, **kwargs)
                usage = record_run_usage(run_output)
                set_span_outputs(span, {
                    "content": getattr(run_output, "content", None),
                    "run_id": getattr(run_output, "run_id", None),
                    "model": getattr(run_output, "model", None),
                    "model_provider": getattr(run_output, "model_provider", None),
                    "usage": usage,
                })
                set_span_attributes(span, {
                    "data_berge.agent": agent_name,
                    "data_berge.llm_usage": usage,
                    "data_berge.model": usage.get("model") if isinstance(usage, dict) else None,
                })
                return run_output
else:  # pragma: no cover
    ObservableAgent = None  # type: ignore[assignment,misc]


@dataclass
class AgentSpec:
    name: str
    role: str
    instructions: str


def _model_id_from_config() -> str:
    if AGNO_BASE_URL:
        return AGNO_MODEL.strip()
    if ":" in AGNO_MODEL:
        return AGNO_MODEL.split(":", 1)[1].strip()
    return AGNO_MODEL.strip()


def normalize_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None
    normalized = base_url.strip().rstrip("/")
    if "generativelanguage.googleapis.com" in normalized and "/openai" not in normalized:
        normalized += "/openai"
    return normalized + "/"


def build_model_config(model_options: dict[str, Any] | None = None) -> Any:
    model_options = model_options or {}
    if AGNO_BASE_URL:
        if CompatibleOpenAILike is None:
            return AGNO_MODEL
        return CompatibleOpenAILike(
            id=_model_id_from_config(),
            api_key=AGNO_API_KEY or "not-provided",
            base_url=normalize_base_url(AGNO_BASE_URL),
            timeout=AGNO_REQUEST_TIMEOUT_SECONDS,
            max_retries=AGNO_MAX_RETRIES,
            **model_options,
        )
    return AGNO_MODEL


def make_agno_agent(
    spec: AgentSpec,
    tools: list[Any] | None = None,
    model_options: dict[str, Any] | None = None,
    **agent_options: Any,
):
    """Create an Agno agent while retaining a dependency-free fallback."""
    if Agent is None:
        return spec
    try:
        return ObservableAgent(
            name=spec.name,
            model=build_model_config(model_options),
            role=spec.role,
            instructions=spec.instructions,
            tools=tools,
            markdown=True,
            **agent_options,
        )
    except Exception:
        return spec
