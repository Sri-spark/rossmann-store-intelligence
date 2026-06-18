"""
Rossmann Store Intelligence — end-to-end pipeline DAG.

    extract_mysql -> load_raw_postgres -> dbt_run -> dbt_test
        -> forecast -> ab_test -> publish_marts

Airflow only orchestrates; each task is a BashOperator invoking an isolated
virtualenv (dbt or analytics) so heavy libraries never clash with Airflow's
own dependencies. All DB credentials arrive via the container environment.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT = "/opt/airflow/project"
DBT_DIR = f"{PROJECT}/dbt/rossmann"
DBT = "/opt/dbt-venv/bin/dbt"
PY = "/opt/analytics-venv/bin/python"

default_args = {
    "owner": "data-eng",
    "retries": 1,
    "retry_delay": timedelta(seconds=30),
}

with DAG(
    dag_id="rossmann_pipeline",
    description="Ingest -> model (dbt star schema) -> forecast -> promo experiment -> publish",
    start_date=datetime(2024, 1, 1),
    schedule=None,  # triggered manually / via `airflow dags test`
    catchup=False,
    default_args=default_args,
    tags=["rossmann", "retail", "elt", "forecast"],
) as dag:

    extract_mysql = BashOperator(
        task_id="extract_mysql",
        bash_command=f"cd {PROJECT} && {PY} etl/pipeline.py extract",
    )

    load_raw_postgres = BashOperator(
        task_id="load_raw_postgres",
        bash_command=f"cd {PROJECT} && {PY} etl/pipeline.py load",
    )

    # --no-partial-parse forces a clean manifest each run: the dbt project dir is
    # bind-mounted and may carry partial-parse state written with host paths,
    # which can otherwise under-collect tests.
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {DBT_DIR} && {DBT} run --no-partial-parse --profiles-dir . --target dev",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_DIR} && {DBT} test --no-partial-parse --profiles-dir . --target dev",
    )

    forecast = BashOperator(
        task_id="forecast",
        bash_command=f"cd {PROJECT} && {PY} analytics/forecasting.py",
    )

    ab_test = BashOperator(
        task_id="ab_test",
        bash_command=f"cd {PROJECT} && {PY} analytics/experiment.py",
    )

    publish_marts = BashOperator(
        task_id="publish_marts",
        bash_command=(
            f"cd {DBT_DIR} && {DBT} docs generate --no-partial-parse --profiles-dir . --target dev "
            f"&& cd {PROJECT} && {PY} etl/pipeline.py publish"
        ),
    )

    (
        extract_mysql
        >> load_raw_postgres
        >> dbt_run
        >> dbt_test
        >> forecast
        >> ab_test
        >> publish_marts
    )
