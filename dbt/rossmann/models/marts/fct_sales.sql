-- Sales fact (grain: one row per store per day).
-- sales_key is a deterministic surrogate = store_key * 1e8 + date_key,
-- unique because date_key (yyyymmdd) < 1e8 and store_key is a small integer.
with s as (
    select
        store_key,
        sale_date,
        (extract(year from sale_date) * 10000
            + extract(month from sale_date) * 100
            + extract(day from sale_date))::bigint as date_key,
        sales,
        customers,
        open_flag,
        promo,
        state_holiday,
        school_holiday
    from {{ ref('stg_sales') }}
)

select
    (store_key::bigint * 100000000 + date_key) as sales_key,
    store_key,
    date_key::int                              as date_key,
    sale_date,
    sales,
    customers,
    open_flag,
    promo,
    state_holiday,
    school_holiday
from s
