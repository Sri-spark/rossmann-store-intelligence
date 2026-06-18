select
    date_day,
    year,
    month,
    day_of_week,
    is_weekend,
    total_sales,
    total_customers,
    open_stores,
    promo_rate,
    avg_sales_per_open_store
from marts.daily_sales
order by date_day
