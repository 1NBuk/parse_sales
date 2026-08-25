FROM apache/airflow:2.9.3-python3.11

USER root

# Java is required for PySpark, even in local (standalone) mode
RUN apt-get update && \
    apt-get install -y --no-install-recommends openjdk-17-jre-headless curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV SPARK_JARS=/opt/airflow/jars

RUN mkdir -p ${SPARK_JARS} && \
    curl -L -o ${SPARK_JARS}/postgresql-42.7.3.jar \
    https://jdbc.postgresql.org/download/postgresql-42.7.3.jar

USER airflow

RUN pip install --no-cache-dir pyspark==3.5.1 psycopg2-binary