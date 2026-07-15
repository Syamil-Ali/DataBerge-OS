# Architecture

## Product shape

Data-Berge OS is a new product architecture inspired by the original Data-Berge prototype. It is not a refactor. The V1 boundary is file analytics for business teams.

## Runtime

- `backend/app/main.py` exposes the API.
- `backend/app/storage/database.py` owns SQLite persistence.
- `backend/app/services/` owns deterministic file loading, profiling, and DuckDB querying.
- `backend/app/agents/` owns the Agno-facing agent layer.
- `backend/app/workflows/` owns repeatable upload, chat, and report flows.
- `frontend/src/App.tsx` owns the cockpit workspace.

## Agent roles

- `TeamManagerAgent`: decides whether to respond conversationally or issue typed assignments to specialists.
- `DataAnalystAgent`: owns intake, profiling, safe SELECT-only DuckDB queries, interpretation, and charts.
- `DataEngineerAgent`: owns data quality, typing, schema trust, joins, cleaning, and readiness.
- `ReportAgent`: owns report planning, narrative hierarchy, presentation, revision, and execution.
- `AnalyticsTeam`: wires the manager and specialists to bounded skills and persistent context.

The LLM owns orchestration decisions. Deterministic profile, SQL, engineering, and report services remain bounded tools that ground agent output. There is no automatic reflection, debate, or retry mode.

Custom reports use a two-phase contract. The Reporter first proposes a content-free `report_plan` containing the audience, goal, ordered sections, purposes, evidence fields, chart intent, and presentation kinds. Revisions receive the complete previous plan and preserve its ID while incrementing its version. Only `Confirm & Generate` freezes the plan and starts Engineer readiness checks, Analyst investigation, Reporter narrative generation, governance review, and artifact storage.

## Approval model

Generated dashboards, charts, and reports are stored as artifacts. Reports are drafts by default. Users must approve or reject artifacts explicitly.

## Future phases

- Add AgentOS endpoints and tracing.
- Add Postgres/object storage.
- Add database/SaaS connectors.
- Add auth, RBAC, audit logs, scheduled refreshes, and evaluation suites.
