# Runbook

## Full stack

```powershell
python run.py
```

This launches:

- frontend: `http://127.0.0.1:5173`
- backend: `http://127.0.0.1:8000/docs`
- MLflow: `http://127.0.0.1:5000`

If you only want backend + frontend:

```powershell
python run.py --skip-mlflow
```

## Backend validation

```powershell
cd backend
python -m compileall app
python run.py
```

Open `http://localhost:8000/docs`.

## Frontend validation

```powershell
cd frontend
npm install
npm run build
npm run dev
```

Open `http://localhost:5173`.

## API smoke test

```powershell
$project = Invoke-RestMethod http://localhost:8000/api/projects
$projectId = $project[0].id
$form = @{ file = Get-Item ..\docs\sample_loan_data.csv }
Invoke-RestMethod -Method Post -Form $form "http://localhost:8000/api/projects/$projectId/datasets"
```

Then use the frontend to ask questions and generate a report.
