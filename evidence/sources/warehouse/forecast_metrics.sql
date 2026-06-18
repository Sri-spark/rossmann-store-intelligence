select
    model,
    mae,
    baseline_mae,
    improvement_pct,
    beats_baseline
from marts.forecast_metrics
order by mae
