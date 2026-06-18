"""
TDD tests for experiment.py — written before the implementation.

Verification Gate 5: the OLS promo coefficient must be reported with an
effect size and a 95% confidence interval (not merely a p-value), and it
must recover a known injected effect on synthetic data.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analytics import experiment as ex  # noqa: E402


def _synthetic_panel(true_lift=1000.0, n_stores=25, n_days=240, seed=7) -> pd.DataFrame:
    """Panel with a known additive promo effect, store + day-of-week effects."""
    rng = np.random.default_rng(seed)
    store_base = rng.uniform(4000, 9000, size=n_stores)
    dow_effect = {1: 600, 2: 200, 3: 0, 4: 0, 5: 400, 6: -300, 7: -1500}
    rows = []
    for s in range(n_stores):
        for d in range(n_days):
            dow = (d % 7) + 1
            promo = int((d // 7) % 2 == (s % 2) and dow <= 6)
            sales = (
                store_base[s]
                + dow_effect[dow]
                + true_lift * promo
                + rng.normal(0, 400)
            )
            rows.append((s + 1, dow, max(sales, 0.0), promo))
    return pd.DataFrame(rows, columns=["Store", "DayOfWeek", "Sales", "Promo"])


def test_cohens_d_known_value():
    a = np.array([2.0, 4.0, 6.0, 8.0])
    b = np.array([1.0, 3.0, 5.0, 7.0])
    # Means differ by 1.0; pooled sd ~ 2.582 -> d ~ 0.387
    d = ex.cohens_d(a, b)
    assert d == pytest.approx(0.387, abs=0.02)


def test_welch_ttest_detects_positive_uplift():
    df = _synthetic_panel(true_lift=1000.0)
    promo = df.loc[df["Promo"] == 1, "Sales"].to_numpy()
    nonpromo = df.loc[df["Promo"] == 0, "Sales"].to_numpy()
    res = ex.welch_ttest(promo, nonpromo)
    assert res["mean_diff"] > 0
    assert res["pvalue"] < 0.05
    assert "cohens_d" in res and res["cohens_d"] > 0


def test_ols_recovers_known_coefficient_with_ci():
    """VERIFICATION GATE 5 (logic)."""
    true_lift = 1200.0
    df = _synthetic_panel(true_lift=true_lift)
    res = ex.ols_promo_lift(df)
    # Required reporting fields:
    for key in ("coef", "ci95_low", "ci95_high", "pvalue", "pct_lift", "cohens_d"):
        assert key in res, f"missing {key}"
    # Recovers the injected effect within tolerance.
    assert res["coef"] == pytest.approx(true_lift, rel=0.15)
    # CI is a proper interval that excludes zero (significant positive effect).
    assert res["ci95_low"] < res["coef"] < res["ci95_high"]
    assert res["ci95_low"] > 0
    print(
        f"\nOLS promo coef={res['coef']:.1f} "
        f"95% CI=[{res['ci95_low']:.1f}, {res['ci95_high']:.1f}] "
        f"pct_lift={res['pct_lift']*100:.2f}% d={res['cohens_d']:.3f} p={res['pvalue']:.2e}"
    )


def test_ols_controls_reduce_confounding():
    """With dow confounded into promo, controls should pull the estimate
    toward the true effect rather than the naive (confounded) difference."""
    true_lift = 800.0
    df = _synthetic_panel(true_lift=true_lift)
    naive_diff = (
        df.loc[df["Promo"] == 1, "Sales"].mean()
        - df.loc[df["Promo"] == 0, "Sales"].mean()
    )
    res = ex.ols_promo_lift(df)
    # The controlled estimate should be closer to truth than the naive diff.
    assert abs(res["coef"] - true_lift) <= abs(naive_diff - true_lift) + 1e-6
