"""
Standalone PySpark job (local mode — no Hadoop/Hive cluster needed).

Reads prices_history from Postgres via JDBC, computes daily
avg/min/max price per (store_id, product_id), and writes the
result back to a new table `price_aggregates_spark`.

Runs inside the airflow-scheduler container, which already has
Java + the Postgres JDBC driver baked in (see Dockerfile.airflow).
"""

import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

PG_HOST = os.environ["PRICES_PG_HOST"]
PG_DB = os.environ["PRICES_PG_DB"]
PG_USER = os.environ["PRICES_PG_USER"]
PG_PASSWORD = os.environ["PRICES_PG_PASSWORD"]

JDBC_URL = f"jdbc:postgresql://{PG_HOST}:5432/{PG_DB}"
JDBC_PROPS = {
    "user": PG_USER,
    "password": PG_PASSWORD,
    "driver": "org.postgresql.Driver",
}


def main():
    spark = (
        SparkSession.builder.appName("PriceAggregation")
        .master("local[*]")
        .config("spark.jars", "/opt/airflow/jars/postgresql-42.7.3.jar")
        .getOrCreate()
    )

    prices = spark.read.jdbc(
        url=JDBC_URL, table="prices_history", properties=JDBC_PROPS
    )

    daily_agg = (
        prices.withColumn("price_date", F.to_date("date"))
        .groupBy("store_id", "product_id", "price_date")
        .agg(
            F.avg("price").alias("avg_price"),
            F.min("price").alias("min_price"),
            F.max("price").alias("max_price"),
            F.count("*").alias("n_observations"),
        )
    )

    daily_agg.write.jdbc(
        url=JDBC_URL,
        table="price_aggregates_spark",
        mode="overwrite",
        properties=JDBC_PROPS,
    )

    print(f"Wrote {daily_agg.count()} aggregated rows to price_aggregates_spark")
    spark.stop()


if __name__ == "__main__":
    main()