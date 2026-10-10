"""SQLite warehouse standing in for BigQuery (raw / staging / curated / audit layers)."""
import os
import sqlite3
import threading

DATA_DIR = os.environ.get("ETL_DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "etl.db")
LANDING_DIR = os.path.join(DATA_DIR, "landing")
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS etl_raw_sales (
  batch_id TEXT, source_system TEXT, transaction_id TEXT, customer_id TEXT,
  amount TEXT, txn_date TEXT, country TEXT, loaded_at TEXT);
CREATE TABLE IF NOT EXISTS etl_staging_sales (
  batch_id TEXT, record_key TEXT, transaction_id TEXT, customer_id TEXT, amount REAL,
  txn_date TEXT, country TEXT, source_system TEXT, ingestion_date TEXT, loaded_at TEXT);
CREATE TABLE IF NOT EXISTS etl_curated_sales (
  record_key TEXT PRIMARY KEY, transaction_id TEXT, customer_id TEXT, amount REAL,
  txn_date TEXT, country TEXT, source_system TEXT, ingestion_date TEXT, batch_id TEXT, loaded_at TEXT);
CREATE TABLE IF NOT EXISTS etl_quarantine (
  batch_id TEXT, source_system TEXT, reason TEXT, record TEXT, quarantined_at TEXT);
CREATE TABLE IF NOT EXISTS etl_audit_runs (
  run_id TEXT PRIMARY KEY, batch_id TEXT, trigger TEXT, status TEXT, start_time TEXT, end_time TEXT,
  rows_loaded INTEGER DEFAULT 0, rows_quarantined INTEGER DEFAULT 0, options TEXT);
CREATE TABLE IF NOT EXISTS etl_audit_tasks (
  run_id TEXT, task_id TEXT, status TEXT, attempts INTEGER DEFAULT 0, start_time TEXT, end_time TEXT,
  rows INTEGER DEFAULT 0, message TEXT, PRIMARY KEY (run_id, task_id));
CREATE TABLE IF NOT EXISTS etl_audit_dq (
  run_id TEXT, batch_id TEXT, source_system TEXT, check_name TEXT, check_status TEXT,
  failed_records INTEGER, checked_at TEXT);
"""


def connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with _lock, connect() as c:
        c.executescript(SCHEMA)


def execute(sql, params=()):
    with _lock, connect() as c:
        c.execute(sql, params)


def query(sql, params=()):
    with _lock, connect() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]
