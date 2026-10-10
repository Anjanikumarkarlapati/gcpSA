-- Raw -> staging: cast, dedupe, standardise, add metadata. Idempotent per batch ({{ ds }}).
DELETE FROM `etl_staging.sales_daily` WHERE ingestion_date = DATE('{{ ds }}');
INSERT INTO `etl_staging.sales_daily`
SELECT CONCAT(source_system, '-', transaction_id) AS record_key, transaction_id, UPPER(TRIM(customer_id)),
       CAST(transaction_amount AS NUMERIC), PARSE_DATE('%Y-%m-%d', transaction_date),
       UPPER(TRIM(country)), source_system, DATE('{{ ds }}') AS ingestion_date, CURRENT_TIMESTAMP() AS loaded_at
FROM (
  SELECT 'source1' AS source_system, transaction_id, customer_id, transaction_amount, transaction_date, country
  FROM `etl_raw.source1` WHERE _PARTITIONDATE = DATE('{{ ds }}')
  UNION ALL SELECT 'source2', TransactionId, CustomerId, Amount, Date, Country
  FROM `etl_raw.source2` WHERE _PARTITIONDATE = DATE('{{ ds }}')
  UNION ALL SELECT 'source3', id, cust, total, dt, ctry
  FROM `etl_raw.source3` WHERE _PARTITIONDATE = DATE('{{ ds }}')
)
WHERE transaction_id IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY source_system, transaction_id ORDER BY transaction_date DESC) = 1;
