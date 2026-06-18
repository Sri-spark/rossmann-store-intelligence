-- Source OLTP schema (MySQL) for Rossmann store sales.
-- Column names are the warehouse team's snake_case mapping of the public
-- Rossmann CSV columns (Store, DayOfWeek, Date, Sales, Customers, Open, Promo,
-- StateHoliday, SchoolHoliday / StoreType, Assortment, CompetitionDistance).
-- Runs automatically on first container start (docker-entrypoint-initdb.d).

CREATE TABLE IF NOT EXISTS store (
    store_id             INT          NOT NULL,
    store_type           CHAR(1),
    assortment           CHAR(1),
    competition_distance FLOAT        NULL,
    PRIMARY KEY (store_id)
);

CREATE TABLE IF NOT EXISTS sales (
    store_id        INT          NOT NULL,   -- Rossmann "Store"
    day_of_week     TINYINT      NULL,       -- Rossmann "DayOfWeek" (1=Mon..7=Sun)
    sale_date       DATE         NOT NULL,   -- Rossmann "Date"
    sales           INT          NULL,       -- Rossmann "Sales"
    customers       INT          NULL,       -- Rossmann "Customers"
    open_flag       TINYINT      NULL,       -- Rossmann "Open"
    promo           TINYINT      NULL,       -- Rossmann "Promo"
    state_holiday   VARCHAR(2)   NULL,       -- Rossmann "StateHoliday" (0/a/b/c)
    school_holiday  TINYINT      NULL,       -- Rossmann "SchoolHoliday"
    KEY idx_store (store_id),
    KEY idx_date (sale_date)
);
