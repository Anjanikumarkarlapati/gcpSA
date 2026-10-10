-- Fails the task (ERROR) when a mandatory check fails; results land in etl_audit.data_quality_results.
INSERT INTO `etl_audit.data_quality_results`
SELECT DATE('{{ ds }}'), 'all', 'duplicate_record_keys',
       IF(COUNT(*) = 0, 'PASSED', 'FAILED'), COUNT(*), CURRENT_TIMESTAMP()
FROM (SELECT record_key FROM `etl_staging.sales_daily` WHERE ingestion_date = DATE('{{ ds }}')
      GROUP BY record_key HAVING COUNT(*) > 1);
ASSERT (SELECT COUNT(*) FROM `etl_staging.sales_daily` WHERE ingestion_date = DATE('{{ ds }}')) > 0 AS 'no rows staged';
ASSERT (SELECT COUNT(DISTINCT source_system) FROM `etl_staging.sales_daily`
        WHERE ingestion_date = DATE('{{ ds }}')) = 3 AS 'a source is missing';
ASSERT NOT EXISTS (SELECT 1 FROM (SELECT record_key FROM `etl_staging.sales_daily`
        WHERE ingestion_date = DATE('{{ ds }}') GROUP BY record_key HAVING COUNT(*) > 1)) AS 'duplicate keys';
