"""
TDD tests for forecasting.py — written before the implementation.

The headline test is `test_best_model_beats_naive_baseline`, which is
Verification Gate 4: the best learned model's walk-forward MAE must
strictly beat the seasonal-naive (last-week value) baseline.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Make the analytics package importable when pytest is run from repo root.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analytics import forecasting as fc  # noqa: E402

DATA = ROOT / "data" / "train.csv"


@pytest.fixture(scope="module")
def daily_series() -> pd.DataFrame:
    assert DATA.exists(), "data/train.csv must be generated first (scripts/generate_data.py)"
    train = pd.read_csv(DATA)
    return fc.daily_series_from_frame(train)


def test_mae_is_zero_for_perfect_prediction():
    assert fc.mae([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 0.0


def test_mae_matches_manual_value():
    assert fc.mae([0.0, 10.0], [5.0, 5.0]) == pytest.approx(5.0)


def test_daily_series_has_expected_shape(daily_series):
    df = daily_series
    # One row per calendar day across the full window.
    assert {"date", "sales", "promo_rate", "open_stores"}.issubset(df.columns)
    assert df["date"].is_monotonic_increasing
    assert df["date"].is_unique
    assert len(df) > 900  # ~2.5 years of daily rows
    assert (df["promo_rate"] >= 0).all() and (df["promo_rate"] <= 1).all()


def test_seasonal_naive_predicts_value_from_one_week_ago(daily_series):
    y = daily_series["sales"].to_numpy(dtype=float)
    test_size = 56
    dates, actual, pred = fc.backtest_seasonal_naive(daily_series, test_size=test_size, season=7)
    assert len(pred) == test_size
    # Each prediction equals the actual value exactly 7 days earlier.
    start = len(y) - test_size
    for i in range(test_size):
        assert pred[i] == pytest.approx(y[start + i - 7])


def test_supervised_features_have_no_future_leakage(daily_series):
    feat = fc.make_supervised(daily_series)
    # lag_7 at a given row must equal sales 7 rows earlier.
    s = daily_series["sales"].to_numpy(dtype=float)
    # Align: make_supervised drops the warm-up rows it cannot fill.
    merged = feat.merge(daily_series[["date", "sales"]], on="date", how="left")
    idx = 30  # safely past the warm-up window
    row = merged.iloc[idx]
    pos = daily_series.index[daily_series["date"] == row["date"]][0]
    assert row["lag_7"] == pytest.approx(s[pos - 7])
    assert row["lag_1"] == pytest.approx(s[pos - 1])


def test_backtests_return_aligned_lengths(daily_series):
    test_size = 28
    for fn in (
        lambda: fc.backtest_seasonal_naive(daily_series, test_size, season=7),
        lambda: fc.backtest_gbm(daily_series, test_size, refit_every=7),
        lambda: fc.backtest_sarima(daily_series, test_size, refit_every=14),
    ):
        dates, actual, pred = fn()
        assert len(dates) == len(actual) == len(pred) == test_size
        assert np.all(np.isfinite(pred))


def test_best_model_beats_naive_baseline(daily_series):
    """VERIFICATION GATE 4."""
    result = fc.run_backtest(daily_series, test_size=84)
    table = result["mae_table"]
    naive_mae = table.loc[table["model"] == "seasonal_naive", "mae"].iloc[0]
    learned = table[table["model"].isin(["sarima", "gbm"])]
    best_mae = learned["mae"].min()
    print("\nMAE comparison:\n", table.to_string(index=False))
    assert best_mae < naive_mae, (
        f"Best learned MAE {best_mae:,.1f} did not beat naive {naive_mae:,.1f}"
    )
