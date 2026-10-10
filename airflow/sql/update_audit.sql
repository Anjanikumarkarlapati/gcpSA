INSERT INTO `etl_audit.etl_runs` (batch_id, run_id, status, rows_loaded, finished_at)
SELECT DATE('{{ ds }}'), '{{ run_id }}', '{{ "success" if dag_run.get_task_instances(state=["failed","upstream_failed"]) | length == 0 else "failed" }}',
       COUNT(*), CURRENT_TIMESTAMP()
FROM `etl_curated.sales` WHERE ingestion_date = DATE('{{ ds }}');
