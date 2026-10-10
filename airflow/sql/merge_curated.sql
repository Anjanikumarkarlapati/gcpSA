MERGE `etl_curated.sales` AS t
USING (SELECT * FROM `etl_staging.sales_daily` WHERE ingestion_date = DATE('{{ ds }}')) AS s
ON t.record_key = s.record_key
WHEN MATCHED THEN UPDATE SET transaction_amount = s.transaction_amount, transaction_date = s.transaction_date,
                             country = s.country, loaded_at = s.loaded_at
WHEN NOT MATCHED THEN INSERT ROW;
