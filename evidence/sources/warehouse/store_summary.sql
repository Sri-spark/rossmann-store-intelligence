select
    store_key,
    store_type,
    assortment_name,
    competition_distance,
    total_sales,
    avg_open_day_sales,
    promo_rate
from marts.store_summary
order by total_sales desc
