select
    forecast_date,
    segment,
    model,
    actual_sales,
    predicted_sales,
    yhat_lower,
    yhat_upper,
    is_future
from marts.forecast
order by forecast_date
