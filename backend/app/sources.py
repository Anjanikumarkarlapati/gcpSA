"""Generates sample data for the three sources into the landing zone, with seeded defects."""
import csv
import json
import os
import random
from datetime import date

from .db import LANDING_DIR

COUNTRIES = ["in", "US", " gb ", "De", "sg"]
SOURCES = {
    "source1": {"label": "Source 1 - CSV in Cloud Storage", "format": "csv", "file": "sales.csv"},
    "source2": {"label": "Source 2 - REST API (NDJSON)", "format": "json", "file": "sales.json"},
    "source3": {"label": "Source 3 - DB export (CSV)", "format": "csv", "file": "orders.csv"},
}
# canonical -> per-source column names (schema standardisation)
COLUMNS = {
    "source1": ["transaction_id", "customer_id", "transaction_amount", "transaction_date", "country"],
    "source2": ["TransactionId", "CustomerId", "Amount", "Date", "Country"],
    "source3": ["id", "cust", "total", "dt", "ctry"],
}


def landing_path(source, batch_id):
    return os.path.join(LANDING_DIR, source, f"ingestion_date={batch_id}", SOURCES[source]["file"])


def generate(source, batch_id, rows=60, drop_column=False, empty=False):
    rng = random.Random(f"{source}-{batch_id}")
    day = date.fromisoformat(batch_id)
    prefix = {"source1": "A", "source2": "B", "source3": "C"}[source]
    records = []
    for i in range(rows):
        records.append([
            f"{prefix}{day:%m%d}{i:04d}",
            f"CUST{rng.randint(1, 40):03d}",
            f"{rng.uniform(5, 500):.2f}",
            day.isoformat(),
            rng.choice(COUNTRIES),
        ])
    if not empty and rows > 10:  # seeded defects
        records.append(list(records[3]))                           # duplicate key
        records.append(["", "CUST001", "10.00", day.isoformat(), "US"])  # null key
        records.append([f"{prefix}BAD1", "CUST002", "12.50", "31-31-2099", "US"])  # bad date
    cols = COLUMNS[source]
    path = landing_path(source, batch_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if empty:
        open(path, "w").close()
        return path
    if drop_column:
        cols = cols[:-1]
        records = [r[:-1] for r in records]
    if SOURCES[source]["format"] == "csv":
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(records)
    else:
        with open(path, "w") as f:
            for r in records:
                f.write(json.dumps(dict(zip(cols, r))) + "\n")
    return path


def read(source, batch_id):
    """Return (header_columns, list_of_dict_rows) as in the landing file."""
    path = landing_path(source, batch_id)
    if SOURCES[source]["format"] == "csv":
        with open(path, newline="") as f:
            r = csv.DictReader(f)
            return r.fieldnames or [], list(r)
    rows = [json.loads(l) for l in open(path) if l.strip()]
    return (list(rows[0].keys()) if rows else []), rows
