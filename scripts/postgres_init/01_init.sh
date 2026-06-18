#!/bin/bash
# Create the analytics warehouse database + raw/staging/marts schemas.
# Runs automatically on first Postgres container start.
# The Airflow metadata database (POSTGRES_DB) is created by the image itself.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE ${POSTGRES_WAREHOUSE_DB}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${POSTGRES_WAREHOUSE_DB}')\gexec
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_WAREHOUSE_DB" <<-EOSQL
    CREATE SCHEMA IF NOT EXISTS raw;
    CREATE SCHEMA IF NOT EXISTS staging;
    CREATE SCHEMA IF NOT EXISTS marts;
EOSQL

echo "Initialized warehouse database '${POSTGRES_WAREHOUSE_DB}' with raw/staging/marts schemas."
