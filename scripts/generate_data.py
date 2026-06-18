"""
Generate synthetic Rossmann-schema store-sales data.

Produces two CSVs that match the public Rossmann Store Sales schema:

  data/train.csv : Store, DayOfWeek, Date, Sales, Customers, Open, Promo,
                   StateHoliday, SchoolHoliday
  data/store.csv : Store, StoreType, Assortment, CompetitionDistance

Design goals (so the downstream pipeline has real signal to model):
  * >= 100 stores over ~2.5 years of *daily* rows.
  * Strong weekly seasonality (Sun mostly closed) + yearly seasonality
    (December peak, summer dip) + a mild upward trend.
  * A genuine promo uplift of ~15% on open days (10-20% target band).
  * Closed-store zeros (Open=0 -> Sales=0, Customers=0) on Sundays and
    a handful of state holidays.
  * Reproducible (fixed seed).

This intentionally does NOT download from Kaggle; it is fully offline.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd

# ── Tunable constants ──────────────────────────────────────────────────────
SEED = 42
N_STORES = 120
START_DATE = "2013-01-01"
END_DATE = "2015-07-31"  # ~2.58 years, the real Rossmann window
PROMO_UPLIFT = 0.15      # +15% on promo days (within the 10-20% target band)

STORE_TYPES = ["a", "b", "c", "d"]
ASSORTMENTS = ["a", "b", "c"]
# A few fixed German-style public holidays (month, day) where stores close.
STATE_HOLIDAYS = {
    (1, 1): "a",    # New Year
    (4, 1): "b",    # (synthetic Easter-ish) public holiday
    (5, 1): "a",    # Labour Day
    (10, 3): "a",   # Unity Day
    (12, 25): "c",  # Christmas
    (12, 26): "c",  # 2nd Christmas day
}


def _store_dimension(rng: np.random.Generator, n_stores: int) -> pd.DataFrame:
    store_type = rng.choice(STORE_TYPES, size=n_stores, p=[0.55, 0.10, 0.20, 0.15])
    assortment = rng.choice(ASSORTMENTS, size=n_stores, p=[0.50, 0.10, 0.40])
    # Competition distance in metres, log-normal, with a few NaNs like the real data.
    comp_dist = np.round(rng.lognormal(mean=8.5, sigma=0.9, size=n_stores) / 10) * 10
    comp_dist = np.clip(comp_dist, 20, 75000)
    nan_mask = rng.random(n_stores) < 0.03
    comp_dist = comp_dist.astype(float)
    comp_dist[nan_mask] = np.nan
    return pd.DataFrame(
        {
            "Store": np.arange(1, n_stores + 1),
            "StoreType": store_type,
            "Assortment": assortment,
            "CompetitionDistance": comp_dist,
        }
    )


def _yearly_factor(doy: np.ndarray) -> np.ndarray:
    """Smooth yearly seasonality: summer dip, strong December peak."""
    base = 1.0 + 0.12 * np.sin(2 * np.pi * (doy - 80) / 365.25)
    # December ramp (day-of-year >= 335) gives a holiday shopping spike.
    dec_boost = np.where(doy >= 335, 0.35 * (doy - 335) / 30.0, 0.0)
    return base + dec_boost


def _dow_factor(dow: np.ndarray) -> np.ndarray:
    """Weekly shape (DayOfWeek 1=Mon ... 7=Sun). Mondays busy, Sat lighter."""
    table = {1: 1.20, 2: 1.05, 3: 1.00, 4: 1.00, 5: 1.10, 6: 0.85, 7: 0.0}
    return np.array([table[d] for d in dow])


def generate(n_stores: int = N_STORES, seed: int = SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    store_df = _store_dimension(rng, n_stores)

    dates = pd.date_range(START_DATE, END_DATE, freq="D")
    n_days = len(dates)
    doy = dates.dayofyear.to_numpy()
    dow = (dates.dayofweek.to_numpy() + 1)  # pandas Mon=0 -> Rossmann Mon=1 ... Sun=7
    month = dates.month.to_numpy()
    day = dates.day.to_numpy()

    # Trend across the whole window (~ +18% from start to end).
    t = np.arange(n_days)
    trend = 1.0 + 0.18 * (t / n_days)
    yearly = _yearly_factor(doy)
    weekly = _dow_factor(dow)

    # State-holiday lookup per date.
    holiday_code = np.array(["0"] * n_days, dtype=object)
    holiday_closed = np.zeros(n_days, dtype=bool)
    for i in range(n_days):
        key = (int(month[i]), int(day[i]))
        if key in STATE_HOLIDAYS:
            holiday_code[i] = STATE_HOLIDAYS[key]
            holiday_closed[i] = True

    # School-holiday blocks (summer + winter), same for all stores.
    school = np.zeros(n_days, dtype=int)
    school[(month >= 7) & (month <= 8)] = 1          # summer break
    school[(month == 12) & (day >= 20)] = 1          # winter break
    school[(month == 1) & (day <= 6)] = 1

    # Per-store base level and noise scale.
    store_base = rng.uniform(3500, 9000, size=n_stores)
    type_mult = {"a": 1.0, "b": 1.6, "c": 0.9, "d": 1.1}
    store_type_mult = store_df["StoreType"].map(type_mult).to_numpy()

    # Market-wide *common* daily demand shock, shared by every store (weather,
    # macro, chain-wide events). Unlike per-store noise, this does NOT cancel
    # when sales are aggregated, so the chain-total series is genuinely
    # stochastic and a model that predicts the conditional mean can beat a
    # naive last-week carry-forward.
    common_shock = rng.normal(1.0, 0.035, size=n_days)

    frames = []
    for s in range(n_stores):
        store_id = s + 1
        # Promo schedule: alternating ~14-day blocks on open trading days
        # (Mon-Sat). Including Saturday keeps the day-of-week mix of promo vs
        # non-promo days balanced, so the *naive* uplift stays near the true
        # injected effect; OLS later still controls for the residual mix.
        block = (t // 14) % 2  # 0/1 alternating fortnights
        promo = ((block == (store_id % 2)) & (dow <= 6)).astype(int)

        # Open logic: closed Sundays, closed on state holidays, plus ~0.5% random closures.
        random_closed = rng.random(n_days) < 0.005
        is_open = np.ones(n_days, dtype=int)
        is_open[dow == 7] = 0
        is_open[holiday_closed] = 0
        is_open[random_closed] = 0

        level = (
            store_base[s]
            * store_type_mult[s]
            * trend
            * yearly
            * weekly
        )
        promo_mult = 1.0 + PROMO_UPLIFT * promo
        noise = rng.normal(1.0, 0.06, size=n_days)  # ~6% idiosyncratic noise
        sales = level * promo_mult * common_shock * noise
        sales = np.where(is_open == 1, sales, 0.0)
        sales = np.clip(np.round(sales), 0, None).astype(int)

        # Customers loosely proportional to sales (~ avg basket 9.5 + noise).
        basket = rng.normal(9.5, 0.8, size=n_days)
        customers = np.where(
            is_open == 1, np.clip(np.round(sales / np.clip(basket, 5, None)), 0, None), 0
        ).astype(int)

        frames.append(
            pd.DataFrame(
                {
                    "Store": store_id,
                    "DayOfWeek": dow,
                    "Date": dates,
                    "Sales": sales,
                    "Customers": customers,
                    "Open": is_open,
                    "Promo": promo,
                    "StateHoliday": holiday_code,
                    "SchoolHoliday": school,
                }
            )
        )

    train_df = pd.concat(frames, ignore_index=True)
    train_df["Date"] = pd.to_datetime(train_df["Date"]).dt.strftime("%Y-%m-%d")
    return train_df, store_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic Rossmann data.")
    parser.add_argument("--stores", type=int, default=N_STORES)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--out", type=str, default=str(Path(__file__).resolve().parents[1] / "data")
    )
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    train_df, store_df = generate(n_stores=args.stores, seed=args.seed)
    train_path = out / "train.csv"
    store_path = out / "store.csv"
    train_df.to_csv(train_path, index=False)
    store_df.to_csv(store_path, index=False)

    # ── Quick integrity summary (doubles as Phase-1 gate evidence) ──
    open_rows = train_df[train_df["Open"] == 1]
    promo_mean = open_rows.loc[open_rows["Promo"] == 1, "Sales"].mean()
    nonpromo_mean = open_rows.loc[open_rows["Promo"] == 0, "Sales"].mean()
    uplift = promo_mean / nonpromo_mean - 1.0
    closed_zeros = int(((train_df["Open"] == 0) & (train_df["Sales"] == 0)).sum())

    print(f"Wrote {train_path}  rows={len(train_df):,}")
    print(f"Wrote {store_path}  rows={len(store_df):,}")
    print(f"Stores                : {train_df['Store'].nunique()}")
    print(f"Date range            : {train_df['Date'].min()} -> {train_df['Date'].max()}")
    print(f"Open-day promo mean    : {promo_mean:,.1f}")
    print(f"Open-day non-promo mean: {nonpromo_mean:,.1f}")
    print(f"Measured promo uplift  : {uplift*100:,.2f}%  (target 10-20%)")
    print(f"Closed-store zero rows : {closed_zeros:,}")


if __name__ == "__main__":
    main()
