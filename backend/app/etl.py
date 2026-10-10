"""Local ETL engine mirroring the Airflow DAG task graph (extract -> validate -> load raw ->
transform staging -> DQ checks -> MERGE curated -> audit). Idempotent per batch_id."""
import json
import threading
import uuid
from datetime import date, datetime, timezone

from . import db, sources

TASKS = (
    ["start"]
    + [t for s in ("1", "2", "3") for t in (f"extract_source_{s}", f"validate_source_{s}", f"load_source_{s}_raw")]
    + ["transform_staging_data", "run_data_quality_checks", "merge_into_curated_table",
       "update_etl_audit_table", "end"]
)
EDGES = {
    "start": [f"extract_source_{s}" for s in "123"],
    **{f"extract_source_{s}": [f"validate_source_{s}"] for s in "123"},
    **{f"validate_source_{s}": [f"load_source_{s}_raw"] for s in "123"},
    **{f"load_source_{s}_raw": ["transform_staging_data"] for s in "123"},
    "transform_staging_data": ["run_data_quality_checks"],
    "run_data_quality_checks": ["merge_into_curated_table"],
    "merge_into_curated_table": ["update_etl_audit_table"],
    "update_etl_audit_table": ["end"],
}
MIN_ROWS = 10
MAX_RETRIES = 3


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TaskFailed(Exception):
    pass


def _parents(task):
    return [p for p, kids in EDGES.items() if task in kids]


def start_run(batch_id=None, trigger="manual", fail_source=None, fail_mode="missing_column"):
    batch_id = batch_id or date.today().isoformat()
    date.fromisoformat(batch_id)  # validate
    run_id = f"run_{batch_id}_{uuid.uuid4().hex[:6]}"
    opts = {"fail_source": fail_source, "fail_mode": fail_mode}
    db.execute("INSERT INTO etl_audit_runs(run_id,batch_id,trigger,status,start_time,options) VALUES(?,?,?,?,?,?)",
               (run_id, batch_id, trigger, "running", now(), json.dumps(opts)))
    for t in TASKS:
        db.execute("INSERT INTO etl_audit_tasks(run_id,task_id,status) VALUES(?,?,?)", (run_id, t, "queued"))
    threading.Thread(target=run_dag, args=(run_id, batch_id, opts), daemon=True).start()
    return run_id


def _set(run_id, task, **kw):
    cols = ", ".join(f"{k}=?" for k in kw)
    db.execute(f"UPDATE etl_audit_tasks SET {cols} WHERE run_id=? AND task_id=?", (*kw.values(), run_id, task))


def run_dag(run_id, batch_id, opts, sync=False):
    status = {t: "queued" for t in TASKS}
    funcs = _task_funcs(run_id, batch_id, opts)
    for task in TASKS:  # TASKS is already in topological order
        if any(status[p] in ("failed", "upstream_failed") for p in _parents(task)):
            status[task] = "upstream_failed"
            _set(run_id, task, status="upstream_failed", message="upstream task failed")
            continue
        _set(run_id, task, status="running", start_time=now())
        for attempt in range(1, MAX_RETRIES + 1):
            _set(run_id, task, attempts=attempt)
            try:
                rows, msg = funcs[task]()
                status[task] = "success"
                _set(run_id, task, status="success", end_time=now(), rows=rows or 0, message=msg or "")
                break
            except TaskFailed as e:  # deterministic failure: no point retrying
                status[task] = "failed"
                _set(run_id, task, status="failed", end_time=now(), message=str(e))
                break
            except Exception as e:  # transient: retry
                if attempt == MAX_RETRIES:
                    status[task] = "failed"
                    _set(run_id, task, status="failed", end_time=now(), message=f"retries exhausted: {e}")
                else:
                    _set(run_id, task, status="up_for_retry", message=str(e))
    failed = any(s in ("failed", "upstream_failed") for s in status.values())
    totals = db.query("SELECT COUNT(*) n FROM etl_curated_sales WHERE batch_id=?", (batch_id,))[0]["n"]
    quar = db.query("SELECT COUNT(*) n FROM etl_quarantine WHERE batch_id=?", (batch_id,))[0]["n"]
    db.execute("UPDATE etl_audit_runs SET status=?, end_time=?, rows_loaded=?, rows_quarantined=? WHERE run_id=?",
               ("failed" if failed else "success", now(), totals, quar, run_id))


def _task_funcs(run_id, batch_id, opts):
    valid_rows = {}  # source -> cleaned rows passing validation

    def noop():
        return 0, ""

    def extract(s):
        def f():
            fail = opts.get("fail_source") == s
            mode = opts.get("fail_mode")
            sources.generate(s, batch_id, drop_column=fail and mode == "missing_column",
                             empty=fail and mode == "empty_file")
            import os
            size = os.path.getsize(sources.landing_path(s, batch_id))
            if size == 0:
                raise TaskFailed("source file is empty")
            return size, f"landed {sources.landing_path(s, batch_id).split('landing/')[-1]}"
        return f

    def validate(s):
        def f():
            cols, rows = sources.read(s, batch_id)
            expected = sources.COLUMNS[s]
            missing = [c for c in expected if c not in cols]
            if missing:
                _dq(run_id, batch_id, s, "required_columns", "FAILED", len(missing))
                raise TaskFailed(f"schema mismatch, missing columns: {missing}")
            if len(rows) < MIN_ROWS:
                _dq(run_id, batch_id, s, "row_count", "FAILED", len(rows))
                raise TaskFailed(f"row count {len(rows)} below minimum {MIN_ROWS}")
            _dq(run_id, batch_id, s, "required_columns", "PASSED", 0)
            _dq(run_id, batch_id, s, "row_count", "PASSED", 0)
            db.execute("DELETE FROM etl_quarantine WHERE batch_id=? AND source_system=?", (batch_id, s))
            good, seen, bad = [], set(), {"null_key": 0, "invalid_date": 0, "duplicate_key": 0, "invalid_amount": 0}
            for r in rows:
                rec = dict(zip(["transaction_id", "customer_id", "amount", "txn_date", "country"],
                               [r[c] for c in expected]))
                reason = None
                if not (rec["transaction_id"] or "").strip():
                    reason = "null_key"
                else:
                    try:
                        d = date.fromisoformat(rec["txn_date"])
                        if abs((d - date.fromisoformat(batch_id)).days) > 30:
                            reason = "invalid_date"
                    except ValueError:
                        reason = "invalid_date"
                    try:
                        float(rec["amount"])
                    except (TypeError, ValueError):
                        reason = reason or "invalid_amount"
                    if not reason and rec["transaction_id"] in seen:
                        reason = "duplicate_key"
                if reason:
                    bad[reason] += 1
                    db.execute("INSERT INTO etl_quarantine VALUES(?,?,?,?,?)",
                               (batch_id, s, reason, json.dumps(r), now()))
                else:
                    seen.add(rec["transaction_id"])
                    good.append(rec)
            for name, n in bad.items():
                _dq(run_id, batch_id, s, name, "QUARANTINED" if n else "PASSED", n)
            valid_rows[s] = good
            return len(good), f"{len(good)} valid, {sum(bad.values())} quarantined"
        return f

    def load_raw(s):
        def f():
            db.execute("DELETE FROM etl_raw_sales WHERE batch_id=? AND source_system=?", (batch_id, s))
            ts = now()
            with db._lock, db.connect() as c:
                c.executemany("INSERT INTO etl_raw_sales VALUES(?,?,?,?,?,?,?,?)",
                              [(batch_id, s, r["transaction_id"], r["customer_id"], r["amount"],
                                r["txn_date"], r["country"], ts) for r in valid_rows[s]])
            return len(valid_rows[s]), "WRITE_TRUNCATE per batch/source"
        return f

    def transform():
        db.execute("DELETE FROM etl_staging_sales WHERE batch_id=?", (batch_id,))
        db.execute("""INSERT INTO etl_staging_sales
          SELECT batch_id, source_system || '-' || TRIM(transaction_id), TRIM(transaction_id),
                 UPPER(TRIM(customer_id)), CAST(amount AS REAL), txn_date, UPPER(TRIM(country)),
                 source_system, batch_id, ? FROM etl_raw_sales WHERE batch_id=?""", (now(), batch_id))
        n = db.query("SELECT COUNT(*) n FROM etl_staging_sales WHERE batch_id=?", (batch_id,))[0]["n"]
        return n, "cast types, trim/upper-case text, add metadata"

    def dq():
        dup = db.query("""SELECT COUNT(*) n FROM (SELECT record_key FROM etl_staging_sales WHERE batch_id=?
                          GROUP BY record_key HAVING COUNT(*)>1)""", (batch_id,))[0]["n"]
        neg = db.query("SELECT COUNT(*) n FROM etl_staging_sales WHERE batch_id=? AND amount<=0", (batch_id,))[0]["n"]
        per = db.query("SELECT COUNT(DISTINCT source_system) n FROM etl_staging_sales WHERE batch_id=?",
                       (batch_id,))[0]["n"]
        _dq(run_id, batch_id, "all", "duplicate_record_keys", "FAILED" if dup else "PASSED", dup)
        _dq(run_id, batch_id, "all", "non_positive_amount", "FAILED" if neg else "PASSED", neg)
        _dq(run_id, batch_id, "all", "all_sources_present", "FAILED" if per < 3 else "PASSED", 3 - per)
        if dup or neg or per < 3:
            raise TaskFailed("data-quality checks failed")
        return 3, "3 checks passed"

    def merge():
        before = db.query("SELECT COUNT(*) n FROM etl_curated_sales")[0]["n"]
        db.execute("""INSERT INTO etl_curated_sales(record_key,transaction_id,customer_id,amount,txn_date,country,
                        source_system,ingestion_date,batch_id,loaded_at)
                      SELECT record_key,transaction_id,customer_id,amount,txn_date,country,source_system,
                             ingestion_date,batch_id,loaded_at FROM etl_staging_sales WHERE batch_id=?
                      ON CONFLICT(record_key) DO UPDATE SET amount=excluded.amount, txn_date=excluded.txn_date,
                        country=excluded.country, batch_id=excluded.batch_id, loaded_at=excluded.loaded_at""",
                   (batch_id,))
        after = db.query("SELECT COUNT(*) n FROM etl_curated_sales")[0]["n"]
        return after - before, f"MERGE: {after - before} inserted, rest updated"

    def audit():
        return 0, "audit row recorded"

    fns = {"start": noop, "end": noop, "transform_staging_data": transform, "run_data_quality_checks": dq,
           "merge_into_curated_table": merge, "update_etl_audit_table": audit}
    for s, n in (("source1", "1"), ("source2", "2"), ("source3", "3")):
        fns[f"extract_source_{n}"] = extract(s)
        fns[f"validate_source_{n}"] = validate(s)
        fns[f"load_source_{n}_raw"] = load_raw(s)
    return fns


def _dq(run_id, batch_id, source, name, status, failed):
    db.execute("INSERT INTO etl_audit_dq VALUES(?,?,?,?,?,?,?)", (run_id, batch_id, source, name, status, failed, now()))
