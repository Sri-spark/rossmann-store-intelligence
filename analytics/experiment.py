"""
Promotional-lift experiment for Rossmann sales.

Two complementary analyses on open trading days:

  1. Welch's t-test (unequal variance) comparing promo vs non-promo daily
     store sales — a quick, assumption-light significance check with an
     effect size (Cohen's d).
  2. OLS regression estimating the promo lift while controlling for store and
     day-of-week fixed effects, which removes the confounding that inflates the
     naive comparison. Reports the coefficient, % lift, Cohen's d, and the
     95% confidence interval — not merely a p-value.

VERIFICATION GATE 5: the OLS promo coefficient is reported with an effect size
and a 95% CI. Host-testable pure functions; `main()` wires to the warehouse
and publishes `marts.promo_effect`.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.formula.api as smf


# ── Effect size ────────────────────────────────────────────────────────────
def cohens_d(a, b) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    na, nb = len(a), len(b)
    va, vb = a.var(ddof=1), b.var(ddof=1)
    pooled = np.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    return float((a.mean() - b.mean()) / pooled)


# ── Welch's t-test ─────────────────────────────────────────────────────────
def welch_ttest(promo, nonpromo) -> dict:
    promo = np.asarray(promo, dtype=float)
    nonpromo = np.asarray(nonpromo, dtype=float)
    t, p = stats.ttest_ind(promo, nonpromo, equal_var=False)
    return {
        "tstat": float(t),
        "pvalue": float(p),
        "mean_promo": float(promo.mean()),
        "mean_nonpromo": float(nonpromo.mean()),
        "mean_diff": float(promo.mean() - nonpromo.mean()),
        "cohens_d": cohens_d(promo, nonpromo),
        "n_promo": int(len(promo)),
        "n_nonpromo": int(len(nonpromo)),
    }


# ── OLS with store + day-of-week fixed effects ─────────────────────────────
def ols_promo_lift(df: pd.DataFrame) -> dict:
    """Estimate additive promo lift controlling for store and day-of-week.

    Expects columns: Sales, Promo (0/1), Store, DayOfWeek.
    """
    d = df[["Sales", "Promo", "Store", "DayOfWeek"]].dropna().copy()
    d["Store"] = d["Store"].astype("category")
    d["DayOfWeek"] = d["DayOfWeek"].astype("category")

    model = smf.ols("Sales ~ Promo + C(Store) + C(DayOfWeek)", data=d).fit()

    coef = float(model.params["Promo"])
    ci = model.conf_int(alpha=0.05).loc["Promo"]
    baseline = float(d.loc[d["Promo"] == 0, "Sales"].mean())
    d_eff = cohens_d(
        d.loc[d["Promo"] == 1, "Sales"], d.loc[d["Promo"] == 0, "Sales"]
    )
    return {
        "coef": coef,
        "ci95_low": float(ci.iloc[0]),
        "ci95_high": float(ci.iloc[1]),
        "pvalue": float(model.pvalues["Promo"]),
        "tstat": float(model.tvalues["Promo"]),
        "pct_lift": float(coef / baseline) if baseline else float("nan"),
        "cohens_d": d_eff,
        "baseline_mean": baseline,
        "r_squared": float(model.rsquared),
        "n_obs": int(model.nobs),
    }


# ── Database wiring (used by Airflow `ab_test` task) ───────────────────────
def warehouse_engine():
    from sqlalchemy import create_engine

    user = os.environ["POSTGRES_USER"]
    pw = os.environ["POSTGRES_PASSWORD"]
    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_WAREHOUSE_DB", "warehouse")
    return create_engine(f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}")


def load_panel_from_db(engine) -> pd.DataFrame:
    sql = """
        SELECT f.store_key      AS "Store",
               d.day_of_week    AS "DayOfWeek",
               f.sales          AS "Sales",
               f.promo          AS "Promo"
        FROM marts.fct_sales f
        JOIN marts.dim_date d ON f.date_key = d.date_key
        WHERE f.open_flag = 1
    """
    return pd.read_sql(sql, engine)


def build_summary(tt: dict, ols: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "coef": ols["coef"],
                "ci95_low": ols["ci95_low"],
                "ci95_high": ols["ci95_high"],
                "pct_lift": ols["pct_lift"],
                "cohens_d": ols["cohens_d"],
                "pvalue": ols["pvalue"],
                "baseline_mean": ols["baseline_mean"],
                "r_squared": ols["r_squared"],
                "n_obs": ols["n_obs"],
                "welch_t": tt["tstat"],
                "welch_p": tt["pvalue"],
                "welch_mean_diff": tt["mean_diff"],
                "mean_promo": tt["mean_promo"],
                "mean_nonpromo": tt["mean_nonpromo"],
            }
        ]
    )


def write_marts(engine, summary: pd.DataFrame):
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS marts"))
    summary.to_sql("promo_effect", engine, schema="marts", if_exists="replace", index=False)


def main():
    engine = warehouse_engine()
    panel = load_panel_from_db(engine)
    print(f"Loaded promo panel: {len(panel):,} open-day store rows")

    promo = panel.loc[panel["Promo"] == 1, "Sales"].to_numpy()
    nonpromo = panel.loc[panel["Promo"] == 0, "Sales"].to_numpy()
    tt = welch_ttest(promo, nonpromo)
    ols = ols_promo_lift(panel)

    print("\n=== Welch's t-test (promo vs non-promo daily store sales) ===")
    print(f"  mean promo     : {tt['mean_promo']:,.1f}")
    print(f"  mean non-promo : {tt['mean_nonpromo']:,.1f}")
    print(f"  mean diff      : {tt['mean_diff']:,.1f}")
    print(f"  Welch t        : {tt['tstat']:,.2f}   p = {tt['pvalue']:.3e}")
    print(f"  Cohen's d      : {tt['cohens_d']:.3f}")

    print("\n=== OLS promo lift (controls: store + day-of-week fixed effects) ===")
    print(f"  promo coefficient : {ols['coef']:,.1f} sales/day")
    print(f"  95% CI            : [{ols['ci95_low']:,.1f}, {ols['ci95_high']:,.1f}]")
    print(f"  relative lift     : {ols['pct_lift'] * 100:.2f}%")
    print(f"  effect size (d)   : {ols['cohens_d']:.3f}")
    print(f"  p-value           : {ols['pvalue']:.3e}")
    print(f"  R^2               : {ols['r_squared']:.3f}  (n={ols['n_obs']:,})")

    summary = build_summary(tt, ols)
    write_marts(engine, summary)
    print("\nWrote marts.promo_effect")


if __name__ == "__main__":
    main()
