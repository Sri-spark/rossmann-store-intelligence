select
    coef,
    ci95_low,
    ci95_high,
    pct_lift,
    cohens_d,
    pvalue,
    baseline_mean,
    r_squared,
    n_obs,
    welch_t,
    welch_p,
    welch_mean_diff,
    mean_promo,
    mean_nonpromo
from marts.promo_effect
