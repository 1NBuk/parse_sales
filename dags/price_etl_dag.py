from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator


default_args = {
    "owner": "veta",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="price_etl_pipeline",
    default_args=default_args,
    description="Scrape retailers -> load to Postgres -> Spark aggregation",
    schedule="0 12 * * *",  # daily at 12:00, same as your old schtasks job
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["thesis", "etl", "spark"],
) as dag:

    # 1) Reuse your existing scraping/ETL script as-is.
    #    Adjust the path below to match where it lives inside /opt/airflow/repo
    #    (mounted from your project root — see docker-compose.yml).
    run_etl = BashOperator(
        task_id="run_scraping_etl",
        bash_command="python /opt/airflow/repo/etl/run_pipeline.py",
    )

    # 2) PySpark local-mode aggregation job (reads/writes Postgres via JDBC).
    def run_spark_aggregation():
        import subprocess

        subprocess.run(
            ["python", "/opt/airflow/spark_jobs/aggregate_prices.py"],
            check=True,
        )

    spark_aggregate = PythonOperator(
        task_id="spark_price_aggregation",
        python_callable=run_spark_aggregation,
    )

    run_etl >> spark_aggregate