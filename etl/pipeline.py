"""
ETL pipeline: MySQL (source OLTP) -> PostgreSQL `raw` schema, plus a publish
step that builds Evidence-facing reporting views over the dbt marts.

Three subcommands, mapped to Airflow tasks:
  extract  -> read `sales` + `store` from MySQL, write to a shared tmp dir
  load     -> load the extracted tables into warehouse `raw` schema
  publish  -> build marts.daily_sales / marts.store_summary reporting views

Self-contained (no intra-project imports) so it can be run by a dedicated
virtualenv inside the Airflow image.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect, text

TMP = Path(os.environ.get("ETL_TMP", "/tmp/rossmann_etl"))
TABLES = ["sales", "store"]


def mysql_engine():
    host = os.environ.get("MYSQL_HOST", "localhost")
    port = os.environ.get("MYSQL_PORT", "3306")
    user = os.environ.get("MYSQL_USER", "rossmann")
    pw = os.environ.get("MYSQL_PASSWORD", "rossmann_pw")
    db = os.environ.get("MYSQL_DATABASE", "rossmann")
    return create_engine(
        f"mysql+pymysql://{user}:{pw}@{host}:{port}/{db}", pool_pre_ping=True
    )


def warehouse_engine():
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ["POSTGRES_USER"]
    pw = os.environ["POSTGRES_PASSWORD"]
    db = os.environ.get("POSTGRES_WAREHOUSE_DB", "warehouse")
    return create_engine(f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}")


def extract() -> None:
    """Extract source tables from MySQL into the shared tmp dir (CSV)."""
    TMP.mkdir(parents=True, exist_ok=True)
    eng = mysql_engine()
    for t in TABLES:
        df = pd.read_sql(f"SELECT * FROM {t}", eng)
        out = TMP / f"{t}.csv"
        df.to_csv(out, index=False)
        print(f"extract: {t} -> {out}  ({len(df):,} rows)")


def load() -> None:
    """Load the extracted tables into the warehouse `raw` schema."""
    eng = warehouse_engine()
    with eng.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))
    insp = inspect(eng)
    for t in TABLES:
        path = TMP / f"{t}.csv"
        if not path.exists():
            raise SystemExit(f"load: missing extracted file {path}; run extract first.")
        df = pd.read_csv(path)
        # Truncate-and-append when the table exists so we never DROP a table that
        # dbt staging views depend on (DROP is blocked by dependents; TRUNCATE
        # is not). Create it on the very first load.
        if insp.has_table(t, schema="raw"):
            with eng.begin() as conn:
                conn.execute(text(f'TRUNCATE TABLE raw."{t}"'))
            mode = "append"
        else:
            mode = "replace"
        df.to_sql(
            t, eng, schema="raw", if_exists=mode, index=False,
            chunksize=10000, method="multi",
        )
        print(f"load: raw.{t}  ({len(df):,} rows, mode={mode})")


def publish() -> None:
    """Build Evidence-facing reporting views over the dbt marts."""
    eng = warehouse_engine()
    stmts = [
        "CREATE SCHEMA IF NOT EXISTS marts",
        """
        CREATE OR REPLACE VIEW marts.daily_sales AS
        SELECT d.date_day,
               d.year,
               d.month,
               d.day_of_week,
               d.is_weekend,
               SUM(f.sales)                                   AS total_sales,
               SUM(f.customers)                               AS total_customers,
               SUM(f.open_flag)                               AS open_stores,
               AVG(f.promo::numeric)                          AS promo_rate,
               SUM(CASE WHEN f.open_flag = 1 THEN f.sales ELSE 0 END)
                   / NULLIF(SUM(f.open_flag), 0)              AS avg_sales_per_open_store
        FROM marts.fct_sales f
        JOIN marts.dim_date d ON f.date_key = d.date_key
        GROUP BY d.date_day, d.year, d.month, d.day_of_week, d.is_weekend
        """,
        """
        CREATE OR REPLACE VIEW marts.store_summary AS
        SELECT s.store_key,
               s.store_type,
               s.assortment_name,
               s.competition_distance,
               SUM(f.sales)                                   AS total_sales,
               AVG(CASE WHEN f.open_flag = 1 THEN f.sales END) AS avg_open_day_sales,
               AVG(f.promo::numeric)                          AS promo_rate
        FROM marts.fct_sales f
        JOIN marts.dim_store s ON f.store_key = s.store_key
        GROUP BY s.store_key, s.store_type, s.assortment_name, s.competition_distance
        """,
    ]
    with eng.begin() as conn:
        for s in stmts:
            conn.execute(text(s))
    # Report row counts as evidence.
    with eng.connect() as conn:
        for obj in ("fct_sales", "dim_store", "dim_date", "daily_sales",
                    "store_summary", "forecast", "promo_effect"):
            try:
                n = conn.execute(text(f"SELECT COUNT(*) FROM marts.{obj}")).scalar()
                print(f"publish: marts.{obj} = {n:,} rows")
            except Exception as exc:  # noqa: BLE001
                print(f"publish: marts.{obj} not available ({exc.__class__.__name__})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rossmann ETL pipeline.")
    parser.add_argument("step", choices=["extract", "load", "publish"])
    args = parser.parse_args()
    {"extract": extract, "load": load, "publish": publish}[args.step]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
