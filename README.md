# Data-Berge OS

Data-Berge OS is a local, single-tenant analytics operating system for business teams. It turns uploaded CSV/XLSX files into profiled datasets, queryable workspaces, generated charts, and executive report drafts that must be approved before final use.

## What is included

- FastAPI backend with SQLite metadata storage.
- Agno-ready agent layer: intake, profiling, query analyst, visualization, reporting, governance, and an analytics team facade.
- DuckDB query engine for safe file analytics.
- React/Vite cockpit UI with upload, profile, chat, artifact rail, and report approval flow.
- Local filesystem storage under `data/`.

## Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python run.py
```

Backend runs at `http://localhost:8000`.

## One-command startup

From the repo root, you can start backend, frontend, and MLflow together:

```powershell
python run.py
```

This starts:

- backend at `http://127.0.0.1:8000`
- frontend at `http://127.0.0.1:5173`
- MLflow at `http://127.0.0.1:5000`

If you only want backend + frontend:

```powershell
python run.py --skip-mlflow
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173` and proxies `/api` to the backend.

## Suggested smoke test

1. Start the stack with `python run.py`.
2. Upload `docs/sample_loan_data.csv`.
3. Ask: `How many rows are in the dataset?`
4. Ask: `What are the top values for Approval?`
5. Review or revise the proposed report plan, then confirm generation.
6. Approve or reject the report in the Reports tab.

## Agno usage

The current V1 uses deterministic analytics services as the source of truth and wraps them in Agno-compatible agent classes. If AgentOS and a model key are configured later, those agent definitions can be served as model-backed agents without changing the API or UI surface.
