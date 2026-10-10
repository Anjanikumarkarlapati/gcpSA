"""Cloud Composer DAG: daily multi-source ETL into BigQuery (see docs/ARCHITECTURE.md).

Each source is processed independently (wait for file -> load raw); transform, DQ,
MERGE and audit (with schema/DQ ASSERTs) run only once all three sources are loaded. SQL lives in airflow/sql and
is idempotent per batch (ds), so retries and reruns never duplicate data.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.empty import EmptyOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.sensors.gcs import GCSObjectsWithPrefixExistenceSensor
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator

LANDING_BUCKET = Variable.get("etl_landing_bucket", default_var="etl-landing-bucket")

default_args = {
    "owner": "data-engineering",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "execution_timeout": timedelta(minutes=30),
    "email_on_failure": True,
    "email": ["data-alerts@example.com"],
}

SOURCES = {  # name -> (glob suffix, BigQuery source format, extra load args)
    "source1": ("*.csv", "CSV", {"skip_leading_rows": 1}),
    "source2": ("*.json", "NEWLINE_DELIMITED_JSON", {}),
    "source3": ("*.csv", "CSV", {"skip_leading_rows": 1}),
}


def run_sql(task_id: str, sql_file: str, **kw):
    """BigQuery job running a templated .sql file (searchpath = airflow/sql)."""
    return BigQueryInsertJobOperator(
        task_id=task_id,
        configuration={"query": {"query": "{% include '" + sql_file + "' %}", "useLegacySql": False}},
        **kw,
    )


with DAG(
    dag_id="daily_multi_source_etl_dag",
    default_args=default_args,
    start_date=datetime(2026, 10, 1),
    schedule="0 2 * * *",
    catchup=False,
    max_active_runs=1,
    template_searchpath=["/home/airflow/gcs/dags/sql"],
    tags=["etl", "daily", "bigquery", "composer"],
) as dag:
    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="end")
    transform = run_sql("transform_staging_data", "transform_staging.sql")
    dq = run_sql("run_data_quality_checks", "data_quality.sql")
    merge = run_sql("merge_into_curated_table", "merge_curated.sql")
    audit = run_sql("update_etl_audit_table", "update_audit.sql", trigger_rule="all_done")

    for n, (src, (pattern, fmt, extra)) in enumerate(SOURCES.items(), start=1):
        prefix = f"{src}/ingestion_date={{{{ ds }}}}/"
        check = GCSObjectsWithPrefixExistenceSensor(
            task_id=f"check_source_{n}_file", bucket=LANDING_BUCKET, prefix=prefix,
            mode="reschedule", poke_interval=300, timeout=60 * 60,
        )
        load = GCSToBigQueryOperator(
            task_id=f"load_source_{n}_raw",
            bucket=LANDING_BUCKET,
            source_objects=[prefix + pattern],
            destination_project_dataset_table=f"etl_raw.{src}${{{{ ds_nodash }}}}",
            source_format=fmt,
            write_disposition="WRITE_TRUNCATE",  # per-partition truncate => idempotent
            create_disposition="CREATE_IF_NEEDED",
            time_partitioning={"type": "DAY"},
            **extra,
        )
        start >> check >> load >> transform

    transform >> dq >> merge >> audit >> end
