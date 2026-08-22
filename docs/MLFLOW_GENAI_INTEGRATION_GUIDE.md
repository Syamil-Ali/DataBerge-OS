# Reusable MLflow GenAI Integration Guide

> Copy this file into another project and give it to the implementation team or coding agent.
> Replace values in angle brackets such as `<APP_NAME>` and adapt module paths to the target project.

This guide was extracted from the working Data-Berge OS integration and generalized for reuse. It covers both GenAI request tracing and conventional experiment runs; use only the parts your project needs.

This guide does **not** create or reimplement MLflow. The normal setup connects the application to an existing MLflow tracking server. Starting a local MLflow server is included only as an optional development convenience.

## Objective

Add MLflow observability to a Python application without making MLflow a runtime dependency of the product's core behavior.

The integration must provide:

- root traces for user-visible AI workflows;
- nested spans for agents, chains, LLM calls, tools, storage, and governance steps;
- latency, model, token-usage, cost, outcome, and error metadata;
- optional framework/provider autologging;
- prompt-registry loading with a code fallback;
- conventional MLflow runs for batch profiling or evaluation jobs;
- privacy-safe user correlation;
- bounded trace payloads;
- graceful behavior when MLflow is disabled or unavailable;
- unit tests that do not require a running MLflow server.

MLflow is observability infrastructure. A tracking outage must never make the application, API, queue worker, or AI workflow fail.

## Non-goals

- Do not use MLflow as the application's primary database.
- Do not put business logic in the observability adapter.
- Do not store authentication tokens, API keys, cookies, database URLs, or request headers in MLflow.
- Do not silently enable raw prompt or completion capture in production.
- Do not require a network connection to MLflow during module import.

## Supported baseline

- Python 3.10 or newer.
- MLflow 3.x with GenAI tracing.
- A dedicated or managed MLflow tracking server for production.
- Local development may use `mlflow server`.

Pin the exact MLflow version validated by the target project. For example:

```text
mlflow==<VALIDATED_VERSION>
```

Regenerate the project's dependency lock after adding it.

## How the Data-Berge OS implementation maps to this guide

The reusable design comes from these concrete integration points:

| Data-Berge OS file or behavior | Reusable concept |
|---|---|
| `backend/app/settings.py` | Environment-based feature flag, tracking URI, experiment, privacy, and prompt settings |
| `backend/app/services/llm_observability.py` | One fault-tolerant adapter for setup, traces, spans, runs, redaction, hashing, and payload limits |
| `backend/data_berge_core/skills/query.py` | Prompt Registry lookup with an in-code fallback |
| `backend/app/agents/data_analyst.py` | Inject registry configuration into the AI component instead of coupling it to application settings |
| `backend/tests/test_report_observability.py` | Fake MLflow spans that verify nesting and failure behavior without a server |
| `run.py --with-mlflow` | Opt-in local tracking server with SQLite metadata and a local artifact directory |

Data-Berge OS uses two complementary MLflow data models:

- GenAI traces represent online chat and report workflows. Root spans contain the user-visible operation, while child spans represent agents, LLM calls, tools, queries, and storage.
- Traditional runs represent batch-style profiling. Parameters describe the job, metrics contain numeric measurements, and JSON artifacts hold bounded summaries.

Keep this separation in other projects. A trace answers “what happened during this request?” A run answers “what were the reproducible inputs and measurements for this job or evaluation?”

## Quick integration path

Use this sequence for a new Python AI project.

### 1. Install and pin MLflow

~~~bash
python -m pip install "mlflow==<VALIDATED_VERSION>"
~~~

Data-Berge OS currently pins `mlflow==3.14.0`. Pin the version you test, commit the dependency file, and regenerate any lock file.

### 2. Connect to an existing MLflow server

Obtain the tracking URI and any required credentials from the team operating MLflow. Configure the application to use that URI; the application should not start or manage the shared MLflow server.

For example:

~~~dotenv
MLFLOW_TRACKING_URI=https://<EXISTING_MLFLOW_HOST>
~~~

Authentication values depend on the existing server and must be supplied through the project's secret manager rather than committed to source control.

#### Optional: start a local server for development only

Create a project-local data directory, then run:

~~~bash
mlflow server --host 127.0.0.1 --port 5000 --backend-store-uri sqlite:///data/mlflow.db --default-artifact-root ./data/mlruns
~~~

SQLite and local artifacts are suitable only for a single-developer environment. This command is not required when an existing MLflow server is available, and it is not a production deployment recipe.

### 3. Configure the application

Add the variables from the configuration contract below to the project's settings layer and `.env.example`. For a local smoke test, set:

~~~dotenv
MLFLOW_TRACKING_ENABLED=true
MLFLOW_TRACKING_URI=http://127.0.0.1:5000
MLFLOW_EXPERIMENT_NAME=<APP_NAME>-local
MLFLOW_LOG_PROMPT_INSTANCES=false
~~~

Keep tracking disabled by default in committed configuration.

### 4. Add the adapter

Create the recommended adapter module and begin with the reference skeleton in this guide. Business modules should import the adapter functions, not `mlflow` directly. Framework-specific autolog setup and Prompt Registry loading are the only reasonable exceptions, and even those should be wrapped so failures fall back safely.

### 5. Instrument one end-to-end workflow

Start with one important request such as `chat.turn`, `document.answer`, or `report.generate`:

1. Open one root trace around the complete workflow.
2. Add child spans around LLM, agent, retrieval, tool, and persistence operations.
3. Record bounded inputs and outputs.
4. Attach model, prompt version, token usage, cost, latency, and outcome when available.
5. Preserve and re-raise the original application exception.

Do not instrument every helper initially. A small number of meaningful spans is easier to search and maintain.

### 6. Verify locally

Trigger one successful request and one controlled failure, then open `http://127.0.0.1:5000` and confirm:

- the expected experiment exists;
- one root trace appears per request;
- child spans have the correct parents and types;
- success and failure states are distinguishable;
- inputs and outputs contain no secrets or prohibited personal data;
- the application still succeeds when the server is stopped or tracking is disabled.

### 7. Add tests before expanding coverage

Mock or fake the MLflow boundary as shown in the testing section. Once disabled, unavailable, success, error, nesting, privacy, and payload-limit cases pass, expand instrumentation to other workflows.

## Configuration contract

Add these environment variables to settings and example environment files:

```dotenv
# Disabled by default. Observability must be an explicit deployment decision.
MLFLOW_TRACKING_ENABLED=false

# Local example; use the private production tracking endpoint when deployed.
MLFLOW_TRACKING_URI=http://localhost:5000

# Prefer one experiment per application or independently operated AI agent.
MLFLOW_EXPERIMENT_NAME=<APP_NAME>

# Keep false unless data governance explicitly permits raw rendered prompts.
MLFLOW_LOG_PROMPT_INSTANCES=false

# A stable HMAC secret used only to pseudonymize application user IDs.
OBSERVABILITY_ID_SECRET=

# Optional prompt registry selection.
MLFLOW_PROMPT_NAME=<PROMPT_NAME>
MLFLOW_PROMPT_VERSION=
MLFLOW_PROMPT_ALIAS=production
MLFLOW_PROMPT_CACHE_TTL_SECONDS=60
```

Production validation should require a strong `OBSERVABILITY_ID_SECRET` whenever tracking is enabled and user-level trace correlation is used.

Provider-specific MLflow authentication should be supplied through the secret mechanism supported by the selected tracking server. Never commit credentials to an environment example.

## Recommended module boundary

Create one adapter such as:

```text
app/
  observability/
    mlflow_runtime.py
```

All application modules should call this adapter. They should not scatter direct MLflow setup, exception handling, redaction, or payload limits throughout business logic.

The adapter API should remain small:

```text
enabled() -> bool
configure() -> bool
configure_framework_autolog() -> None
workflow_trace(...) -> ContextManager[Span | None]
trace_span(...) -> ContextManager[Span | None]
set_span_outputs(span, outputs) -> None
set_span_attributes(span, attributes) -> None
complete_trace(span, ...) -> None
tracked_run(...) -> ContextManager
load_prompt_or_fallback(...) -> PromptSelection
pseudonymous_user_hash(user_id) -> str | None
```

## Reference adapter skeleton

Use this as a starting point. Connect the `settings` names to the target project's configuration system.

```python
from __future__ import annotations

import hashlib
import hmac
import json
import time
from contextlib import contextmanager
from typing import Any, Iterator

from app import settings

try:
    import mlflow
    from mlflow.tracing.constant import SpanAttributeKey, TraceMetadataKey
except Exception:
    # Observability must remain optional and non-fatal.
    mlflow = None
    SpanAttributeKey = None
    TraceMetadataKey = None


_CONFIGURED = False
_CONFIG_RETRY_AT = 0.0


def enabled() -> bool:
    return bool(settings.MLFLOW_TRACKING_ENABLED and mlflow is not None)


def configure() -> bool:
    """Configure once, with a cooldown after tracking-server failures."""
    global _CONFIGURED, _CONFIG_RETRY_AT
    if _CONFIGURED:
        return True
    if not enabled() or time.monotonic() < _CONFIG_RETRY_AT:
        return False
    try:
        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)
        _CONFIGURED = True
        return True
    except Exception:
        # Log locally at warning level if the project has a logger.
        _CONFIG_RETRY_AT = time.monotonic() + 30
        return False


def stable_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def pseudonymous_user_hash(user_id: str | None) -> str | None:
    secret = settings.OBSERVABILITY_ID_SECRET
    if not user_id or not secret:
        return None
    return hmac.new(
        secret.encode("utf-8"),
        str(user_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]


def safe_payload(value: Any, max_chars: int = 250_000) -> Any:
    """Make a JSON-safe, bounded payload for trace inputs and outputs."""
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            default=str,
            allow_nan=False,
        )
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
def workflow_trace(
    name: str,
    *,
    inputs: Any,
    tags: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> Iterator[Any | None]:
    """Create a root trace and preserve application exceptions."""
    if not enabled() or not configure():
        yield None
        return

    try:
        manager = mlflow.start_span(name=name, span_type="CHAIN")
    except Exception:
        yield None
        return

    with manager as span:
        try:
            span.set_inputs(safe_payload(inputs))
            mlflow.update_current_trace(
                tags={
                    key: str(value)[:500]
                    for key, value in (tags or {}).items()
                    if value is not None
                },
                metadata={
                    key: str(value)[:1_000]
                    for key, value in (metadata or {}).items()
                    if value is not None
                },
                session_id=session_id,
                state="IN_PROGRESS",
            )
        except Exception:
            pass

        try:
            yield span
        except Exception as exc:
            set_span_outputs(
                span,
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:1_000],
                },
            )
            try:
                span.set_status("ERROR")
                mlflow.update_current_trace(
                    tags={"has_error": "true"},
                    metadata={"error_type": type(exc).__name__},
                    response_preview=str(exc)[:500],
                    state="ERROR",
                )
            except Exception:
                pass
            raise
        finally:
            try:
                if hasattr(mlflow, "flush_trace_async_logging"):
                    mlflow.flush_trace_async_logging()
            except Exception:
                pass


@contextmanager
def trace_span(
    name: str,
    *,
    span_type: str = "CHAIN",
    inputs: Any | None = None,
    attributes: dict[str, Any] | None = None,
    require_active_trace: bool = True,
) -> Iterator[Any | None]:
    """Create a child span without affecting application execution."""
    if (
        not enabled()
        or not configure()
        or (require_active_trace and not has_active_trace())
    ):
        yield None
        return
    try:
        manager = mlflow.start_span(
            name=name,
            span_type=span_type,
            attributes=attributes,
        )
    except Exception:
        yield None
        return

    with manager as span:
        if inputs is not None:
            try:
                span.set_inputs(safe_payload(inputs))
            except Exception:
                pass
        yield span


def set_span_outputs(span: Any | None, outputs: Any) -> None:
    if span is None:
        return
    try:
        span.set_outputs(safe_payload(outputs))
    except Exception:
        return


def set_span_attributes(
    span: Any | None,
    attributes: dict[str, Any],
) -> None:
    if span is None:
        return
    try:
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, safe_payload(value, max_chars=20_000))
    except Exception:
        return


def complete_trace(
    span: Any | None,
    *,
    outputs: dict[str, Any],
    metadata: dict[str, Any],
    model: str | None = None,
    token_usage: dict[str, Any] | None = None,
    cost: dict[str, Any] | None = None,
) -> None:
    set_span_outputs(span, outputs)
    if span is None or mlflow is None:
        return

    try:
        if SpanAttributeKey is not None:
            if model:
                span.set_attribute(SpanAttributeKey.MODEL, model)
            if token_usage:
                span.set_attribute(SpanAttributeKey.CHAT_USAGE, token_usage)

        trace_metadata = {
            key: str(value)[:1_000]
            for key, value in metadata.items()
            if value is not None
        }
        if TraceMetadataKey is not None:
            if model:
                trace_metadata[TraceMetadataKey.MODEL_ID] = model
            if token_usage:
                trace_metadata[TraceMetadataKey.TOKEN_USAGE] = json.dumps(token_usage)
            if cost:
                trace_metadata[TraceMetadataKey.COST] = json.dumps(cost)

        mlflow.update_current_trace(
            metadata=trace_metadata,
            response_preview=str(outputs.get("summary") or "Completed")[:500],
            state="OK",
            model_id=model,
        )
    except Exception:
        return
```

## Instrumentation pattern

Trace business workflows, not HTTP controller plumbing. The API route or queue consumer should call an instrumented workflow service.

```python
from app.observability.mlflow_runtime import (
    complete_trace,
    pseudonymous_user_hash,
    set_span_outputs,
    trace_span,
    workflow_trace,
)


def generate_report(request, dataset, user_id, session_id):
    tags = {
        "app.kind": "report",
        "dataset_id": dataset["id"],
        "has_error": "false",
    }
    user_hash = pseudonymous_user_hash(user_id)
    if user_hash:
        tags["app.user_hash"] = user_hash

    with workflow_trace(
        "report.generate",
        inputs={
            "dataset_id": dataset["id"],
            "template": request.template,
        },
        tags=tags,
        metadata={"template": request.template},
        session_id=session_id,
    ) as root:
        with trace_span(
            "report.investigate",
            span_type="AGENT",
            inputs={"dataset_id": dataset["id"]},
        ) as investigation_span:
            findings = investigate(dataset)
            set_span_outputs(
                investigation_span,
                {
                    "finding_count": len(findings),
                    "findings": findings,
                },
            )

        with trace_span(
            "report.persist",
            span_type="TOOL",
            inputs={"operation": "create"},
        ) as storage_span:
            artifact = save_report(findings)
            set_span_outputs(
                storage_span,
                {"artifact_id": artifact["id"]},
            )

        complete_trace(
            root,
            outputs={
                "summary": "Report generated",
                "artifact_id": artifact["id"],
            },
            metadata={"finding_count": len(findings)},
            model="<MODEL_ID>",
            token_usage={"input_tokens": 0, "output_tokens": 0},
        )
        return artifact
```

## Span conventions

Use a stable taxonomy across the project:

| Operation | Span type | Example |
|---|---|---|
| End-to-end workflow | `CHAIN` | `chat.turn`, `report.generate` |
| Agent decision or handoff | `AGENT` | `report.investigate` |
| Direct model call | `LLM` | `analyst.plan` |
| Database/query/external API | `TOOL` | `dataset.query` |
| Deterministic composition | `CHAIN` | `report.compose` |

Use low-cardinality names. Put IDs in tags or metadata, not in span names. For example, use `dataset.query`, not `dataset.query.<dataset_id>`.

Recommended trace fields:

- workflow type and version;
- application release or commit SHA;
- pseudonymous user hash;
- session, job, project, dataset, and artifact identifiers where policy permits;
- model and provider;
- prompt name and immutable version or alias resolution;
- token usage and cost;
- elapsed time;
- routing decision, agent, skill, and tool;
- success, handled fallback, or error state;
- output counts and hashes instead of unbounded raw collections.

## Framework and provider autologging

Use one supported MLflow autolog integration when it adds useful model/tool detail:

```python
def configure_framework_autolog() -> None:
    if not enabled() or not configure():
        return
    try:
        import mlflow.agno

        mlflow.agno.autolog(log_traces=True, silent=True)
    except Exception:
        return
```

Call this once during application or worker startup, after importing the framework classes that need instrumentation.

Replace `mlflow.agno.autolog()` with the official integration for the project's framework or model provider.

Important privacy rule: framework autologging may capture prompts and completions. If production policy prohibits that, do not enable autologging until the chosen integration is configured to suppress content. Use manual, redacted spans instead.

## Prompt Registry with code fallback

The application must continue working when MLflow or the registry is unavailable.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptSelection:
    template: str
    name: str
    version: str
    source: str
    uri: str


def load_prompt_or_fallback(
    *,
    name: str,
    fallback_template: str,
    version: str | None = None,
    alias: str | None = "production",
    cache_ttl_seconds: int = 60,
) -> PromptSelection:
    if enabled() and configure():
        try:
            if version:
                uri = f"prompts:/{name}/{version}"
            else:
                uri = f"prompts:/{name}@{alias or 'latest'}"
            prompt = mlflow.genai.load_prompt(
                uri,
                cache_ttl_seconds=cache_ttl_seconds,
            )
            return PromptSelection(
                template=str(prompt.template),
                name=str(prompt.name),
                version=str(prompt.version),
                source="mlflow",
                uri=uri,
            )
        except Exception:
            pass

    return PromptSelection(
        template=fallback_template,
        name=name,
        version="code-fallback",
        source="code",
        uri="",
    )
```

Rules:

- Store a known-good prompt in source control.
- Prefer an immutable numeric prompt version for strict reproducibility.
- An alias such as `production` is useful for controlled promotion.
- Record the resolved prompt name and version on every trace.
- Do not implement prompt rendering with ad-hoc string replacement if the registry prompt object's `format()` method can be used safely.
- Never make prompt-registry availability a requirement for serving requests.

## Traditional MLflow runs

Use `mlflow.start_run()` for batch-style operations such as:

- dataset profiling;
- offline evaluations;
- benchmark suites;
- prompt/model comparisons;
- model training;
- reproducible data-processing jobs.

For high-volume online requests, use GenAI traces rather than opening a traditional run for every request.

Log:

- small scalar parameters;
- numeric metrics;
- bounded JSON summaries;
- hashes and versions;
- approved evaluation artifacts.

Do not log full uploaded datasets by default.

## Queue and worker behavior

The worker process must call `configure()` and optional framework autologging during its own startup.

For background jobs:

- create a root trace inside the worker where execution occurs;
- use the durable job ID as `session_id` or correlation metadata;
- include the API request ID or originating trace ID if the queue transports safe trace context;
- flush asynchronous trace logging before a short-lived worker process exits;
- do not retry a successful business job because trace export failed.

## Availability and performance rules

- MLflow calls must be wrapped so telemetry failures are non-fatal.
- Do not perform an uncached tracking-server health request on every application request.
- Use a short timeout and a cached/background reachability result if probing is required.
- Keep the adapter import-safe when MLflow is not installed.
- Bound input/output payload size before serialization or upload.
- Keep tags and span names low cardinality.
- Avoid logging large tabular results; log row counts, previews, hashes, and artifact references.
- Preserve the original business exception and traceback.

## Privacy and security checklist

- [ ] Raw prompt logging is disabled by default.
- [ ] Raw completion logging is explicitly governed.
- [ ] User IDs are HMAC-pseudonymized with a dedicated secret.
- [ ] Secrets, cookies, authorization headers, and connection strings are excluded.
- [ ] Uploaded source files and full datasets are not logged.
- [ ] Trace payloads are size bounded.
- [ ] Error strings are truncated and reviewed for sensitive content.
- [ ] MLflow endpoint traffic uses TLS outside a private trusted network.
- [ ] Access control and retention are configured on the tracking server.
- [ ] Production and non-production experiments are separated.

## Testing requirements

Use a fake MLflow implementation or mocks. Unit tests must verify:

1. Disabled tracking performs no MLflow calls.
2. Missing MLflow dependency does not break imports or workflows.
3. Tracking-server failure does not change the business result.
4. Child spans are nested under the root span.
5. Successful traces finish in `OK` state.
6. Unhandled workflow exceptions finish in `ERROR` state and are re-raised.
7. Handled agent/provider failures create an error child span while the root records the fallback outcome.
8. Oversized payloads are truncated and include a stable hash.
9. User hashes are stable for the same secret and differ across users.
10. Prompt-registry failure selects the code fallback.
11. Token usage, model ID, and cost are recorded when available.
12. Raw prompt instances remain absent when the privacy flag is false.

Add one optional integration test, disabled by default, that sends a trace to a real test MLflow server and confirms it is queryable.

## Deployment checklist

1. Provision a dedicated or managed MLflow tracking server.
2. Configure its production backend database, artifact storage, authentication, TLS, backup, and retention.
3. Create the application experiment.
4. Set the tracking URI and secret credentials in the deployment platform.
5. Generate a strong `OBSERVABILITY_ID_SECRET`.
6. Decide whether raw prompt/completion capture is legally and operationally acceptable.
7. Register and promote the initial prompt version if using Prompt Registry.
8. Deploy with tracking disabled and verify normal application behavior.
9. Enable tracking in staging.
10. Verify success traces, error traces, nested spans, token usage, and fallback behavior.
11. Load-test with tracing enabled and compare latency/resource usage.
12. Enable production tracking with alerts for exporter failures and storage growth.
13. Perform a retention and restore drill.

## Acceptance criteria

The integration is complete when:

- the application behaves identically with MLflow enabled, disabled, or unreachable;
- each important AI workflow produces one searchable root trace;
- agent, tool, LLM, and storage operations appear as correctly nested spans;
- errors and handled fallbacks are distinguishable;
- model, prompt version, tokens, cost, latency, and outcome are available when supplied;
- no prohibited sensitive values appear in traces;
- prompt-registry failure uses a tested code fallback;
- workers emit and flush their own traces;
- unit tests pass without an MLflow server;
- a staging integration test confirms traces arrive at the configured experiment;
- operational ownership, retention, authentication, backup, and monitoring are documented.

## Official references

- MLflow tracing quickstart: https://mlflow.org/docs/latest/genai/tracing/quickstart
- Automatic tracing integrations: https://mlflow.org/docs/latest/genai/tracing/integrations/
- Agno tracing integration: https://mlflow.org/docs/latest/genai/tracing/integrations/listing/agno/
- Prompt Registry: https://mlflow.org/docs/latest/genai/prompt-registry/
- Using prompts in applications: https://mlflow.org/docs/latest/genai/prompt-registry/use-prompts-in-apps/

