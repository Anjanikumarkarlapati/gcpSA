# Daily Multi-Source ETL Orchestrator

Cloud Composer / Airflow pipeline that loads three sources into BigQuery daily, plus a web app to run and monitor it.

| Folder | What it is |
|---|---|
| `airflow/` | Production DAG (`daily_multi_source_etl_dag`, 02:00 daily) + BigQuery SQL. Upload `dags/*` and `sql/` to the Composer DAGs bucket (`sql/` as `dags/sql/`). |
| `backend/` | FastAPI service with a **local ETL engine** mirroring the DAG task graph (extract → validate → load raw → transform → DQ → MERGE → audit), using SQLite in place of BigQuery and a local folder in place of the GCS landing zone. |
| `frontend/` | React (Vite) dashboard: trigger runs, live task graph, run history, data-quality results, curated data, quarantine. |

## Run locally
```bash
pip install -r backend/requirements.txt
(cd frontend && npm install && npm run build)
uvicorn app.main:app --app-dir backend --port 8000   # UI + API at http://localhost:8000
# dev mode: `npm run dev` in frontend/ (proxies /api to :8000)
(cd backend && pytest)
```
Env: `ETL_SCHEDULER=1` enables the daily trigger (hour `ETL_SCHEDULE_HOUR`, default 2); `ETL_DATA_DIR` sets storage.

## Behaviour
- Each source is processed independently; a failing source fails only its branch, and transform/MERGE become `upstream_failed`.
- Invalid rows (null key, bad date, duplicate key) go to quarantine; missing columns or too few rows fail the task.
- Reruns of the same batch date are idempotent (per-batch delete + MERGE on `record_key`).
- API: `GET /api/config|stats|runs|runs/{id}|curated|quarantine`, `POST /api/runs`, `POST /api/schedule`.

The Airflow DAG is only syntax-checked here (running it needs Composer + GCP).
