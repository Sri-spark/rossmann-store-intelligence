# Custom Airflow image for the Rossmann pipeline.
#
# Airflow only ORCHESTRATES (BashOperators). The heavy work runs in two
# isolated virtualenvs so nothing clashes with Airflow's own pinned deps:
#   /opt/dbt-venv       -> dbt-postgres (transform)
#   /opt/analytics-venv -> pandas/numpy/scipy/sklearn/statsmodels/etc. (ETL,
#                          forecasting, experiment)
FROM apache/airflow:2.10.5-python3.12

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── dbt in an isolated venv ────────────────────────────────────────────────
RUN python -m venv /opt/dbt-venv \
    && /opt/dbt-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/dbt-venv/bin/pip install --no-cache-dir "dbt-postgres==1.9.*"

# ── analytics / ETL in an isolated venv ────────────────────────────────────
COPY analytics/requirements.txt /tmp/analytics-requirements.txt
RUN python -m venv /opt/analytics-venv \
    && /opt/analytics-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/analytics-venv/bin/pip install --no-cache-dir -r /tmp/analytics-requirements.txt

USER airflow
