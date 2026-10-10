import json
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, etl, sources

SCHEDULE_HOUR = int(os.environ.get("ETL_SCHEDULE_HOUR", "2"))  # daily at 02:00 server time
state = {"schedule_enabled": os.environ.get("ETL_SCHEDULER", "0") == "1", "last_scheduled": None}


def _scheduler():
    while True:
        n = datetime.now()
        today = date.today().isoformat()
        if state["schedule_enabled"] and n.hour == SCHEDULE_HOUR and state["last_scheduled"] != today:
            state["last_scheduled"] = today
            etl.start_run(today, trigger="scheduled")
        time.sleep(30)


@asynccontextmanager
async def lifespan(_):
    db.init()
    threading.Thread(target=_scheduler, daemon=True).start()
    yield


app = FastAPI(title="Daily Multi-Source ETL Orchestrator", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class RunRequest(BaseModel):
    batch_id: str | None = None
    fail_source: str | None = None
    fail_mode: str = "missing_column"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config():
    return {"dag_id": "daily_multi_source_etl_dag", "schedule": f"0 {SCHEDULE_HOUR} * * *",
            "schedule_enabled": state["schedule_enabled"], "sources": sources.SOURCES,
            "tasks": etl.TASKS, "edges": etl.EDGES, "max_retries": etl.MAX_RETRIES}


@app.post("/api/schedule")
def set_schedule(enabled: bool):
    state["schedule_enabled"] = enabled
    return {"schedule_enabled": enabled}


@app.post("/api/runs", status_code=202)
def trigger(req: RunRequest):
    if req.fail_source and req.fail_source not in sources.SOURCES:
        raise HTTPException(422, "unknown source")
    if req.fail_mode not in ("missing_column", "empty_file"):
        raise HTTPException(422, "unknown fail_mode")
    try:
        run_id = etl.start_run(req.batch_id, "manual", req.fail_source, req.fail_mode)
    except ValueError:
        raise HTTPException(422, "batch_id must be YYYY-MM-DD")
    return {"run_id": run_id}


@app.get("/api/runs")
def runs(limit: int = 30):
    return db.query("SELECT * FROM etl_audit_runs ORDER BY start_time DESC, rowid DESC LIMIT ?", (limit,))


@app.get("/api/runs/{run_id}")
def run(run_id: str):
    r = db.query("SELECT * FROM etl_audit_runs WHERE run_id=?", (run_id,))
    if not r:
        raise HTTPException(404, "run not found")
    tasks = {t["task_id"]: t for t in db.query("SELECT * FROM etl_audit_tasks WHERE run_id=?", (run_id,))}
    return {**r[0], "options": json.loads(r[0]["options"] or "{}"),
            "tasks": [tasks[t] for t in etl.TASKS if t in tasks],
            "dq": db.query("SELECT * FROM etl_audit_dq WHERE run_id=? ORDER BY rowid", (run_id,))}


@app.get("/api/curated")
def curated(limit: int = Query(50, le=500), source: str | None = None, batch_id: str | None = None):
    where, p = [], []
    if source:
        where.append("source_system=?"); p.append(source)
    if batch_id:
        where.append("batch_id=?"); p.append(batch_id)
    w = "WHERE " + " AND ".join(where) if where else ""
    return {"rows": db.query(f"SELECT * FROM etl_curated_sales {w} ORDER BY txn_date DESC, record_key LIMIT ?", (*p, limit)),
            "summary": db.query(f"""SELECT source_system, COUNT(*) rows, ROUND(SUM(amount),2) total_amount
                                    FROM etl_curated_sales {w} GROUP BY source_system""", tuple(p))}


@app.get("/api/quarantine")
def quarantine(limit: int = 100):
    return db.query("SELECT * FROM etl_quarantine ORDER BY quarantined_at DESC LIMIT ?", (limit,))


@app.get("/api/stats")
def stats():
    r = db.query("""SELECT COUNT(*) total, SUM(status='success') ok, SUM(status='failed') failed,
                    SUM(status='running') running FROM etl_audit_runs""")[0]
    dur = db.query("""SELECT AVG(strftime('%s',end_time)-strftime('%s',start_time)) d FROM etl_audit_runs
                      WHERE end_time IS NOT NULL""")[0]["d"]
    return {"runs": r["total"], "success": r["ok"] or 0, "failed": r["failed"] or 0, "running": r["running"] or 0,
            "success_rate": round(100 * (r["ok"] or 0) / r["total"], 1) if r["total"] else None,
            "avg_duration_s": round(dur, 1) if dur is not None else None,
            "curated_rows": db.query("SELECT COUNT(*) n FROM etl_curated_sales")[0]["n"],
            "quarantined_rows": db.query("SELECT COUNT(*) n FROM etl_quarantine")[0]["n"]}


_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(_dist, "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):  # client-side routes (react-router) fall back to index.html
        f = os.path.join(_dist, path)
        return FileResponse(f if path and os.path.isfile(f) else os.path.join(_dist, "index.html"))
