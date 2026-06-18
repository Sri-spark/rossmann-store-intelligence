---
title: Rossmann Store Intelligence
---

Retail analytics for the Rossmann store chain — sales trends, a demand forecast
with an uncertainty band, and the measured causal lift from promotions. All data
flows MySQL → Postgres warehouse → dbt star schema → forecasting & experiment → here.

```sql kpi
select
    sum(total_sales)                as total_sales,
    avg(total_sales)                as avg_daily_sales,
    sum(total_customers)            as total_customers,
    min(date_day)                   as first_day,
    max(date_day)                   as last_day
from warehouse.daily_sales
```

```sql store_count
select count(*) as n_stores from warehouse.store_summary
```

<BigValue data={kpi} value=total_sales fmt='#,##0' title="Total sales"/>
<BigValue data={kpi} value=avg_daily_sales fmt='#,##0' title="Avg sales / day"/>
<BigValue data={store_count} value=n_stores title="Stores"/>
<BigValue data={kpi} value=last_day title="Latest date"/>

## Sales trend

```sql monthly
select
    date_trunc('month', date_day) as month,
    sum(total_sales)              as total_sales,
    sum(total_customers)          as total_customers
from warehouse.daily_sales
group by 1
order by 1
```

Monthly chain-wide sales show clear yearly seasonality (December peaks) and a
gentle upward trend.

<LineChart data={monthly} x=month y=total_sales yAxisTitle="Total sales" title="Monthly total sales"/>

```sql daily_recent
select date_day, total_sales
from warehouse.daily_sales
where date_day >= (select max(date_day) - interval 120 day from warehouse.daily_sales)
order by date_day
```

<LineChart data={daily_recent} x=date_day y=total_sales title="Daily total sales (last 120 days)" yAxisTitle="Total sales"/>

## Demand forecast

```sql forecast_backtest
select forecast_date, actual_sales, predicted_sales, model
from warehouse.forecast
where is_future = false
order by forecast_date
```

```sql forecast_future
select forecast_date, predicted_sales, yhat_lower, yhat_upper, model
from warehouse.forecast
where is_future = true
order by forecast_date
```

```sql metrics
select model, mae, baseline_mae, improvement_pct, beats_baseline
from warehouse.forecast_metrics
order by mae
```

**Walk-forward backtest** — the chosen model (lowest MAE) tracked against actuals
on a held-out window:

<LineChart data={forecast_backtest} x=forecast_date y={['actual_sales','predicted_sales']} title="Backtest: actual vs predicted" yAxisTitle="Total sales"/>

**Forward forecast with a 95% band** (lower / mean / upper):

<LineChart data={forecast_future} x=forecast_date y={['yhat_lower','predicted_sales','yhat_upper']} title="42-day forecast with 95% band" yAxisTitle="Total sales"/>

Model comparison (MAE vs the naive seasonal baseline — lower is better):

<DataTable data={metrics}>
  <Column id=model/>
  <Column id=mae fmt='#,##0'/>
  <Column id=baseline_mae fmt='#,##0'/>
  <Column id=improvement_pct fmt='0.0"%"'/>
  <Column id=beats_baseline/>
</DataTable>

## Promotional lift

```sql promo
select * from warehouse.promo_effect
```

```sql promo_bars
select 'promo' as cohort, mean_promo as avg_sales from warehouse.promo_effect
union all
select 'non-promo' as cohort, mean_nonpromo as avg_sales from warehouse.promo_effect
```

The OLS estimate controls for store and day-of-week fixed effects, so it reports
the *causal* promo lift rather than the confounded raw difference.

<BigValue data={promo} value=coef fmt='#,##0' title="Promo lift (sales/day)"/>
<BigValue data={promo} value=pct_lift fmt='0.0%' title="Relative lift"/>
<BigValue data={promo} value=cohens_d fmt='0.00' title="Effect size (Cohen's d)"/>

<DataTable data={promo}>
  <Column id=coef title="OLS coef" fmt='#,##0'/>
  <Column id=ci95_low title="95% CI low" fmt='#,##0'/>
  <Column id=ci95_high title="95% CI high" fmt='#,##0'/>
  <Column id=pct_lift title="% lift" fmt='0.0%'/>
  <Column id=pvalue title="p-value" fmt='0.000e+0'/>
  <Column id=r_squared title="R²" fmt='0.000'/>
</DataTable>

<BarChart data={promo_bars} x=cohort y=avg_sales title="Mean daily store sales: promo vs non-promo" yAxisTitle="Avg sales"/>

## Stores

```sql stores
select store_key, store_type, assortment_name, competition_distance, total_sales, avg_open_day_sales, promo_rate
from warehouse.store_summary
order by total_sales desc
limit 20
```

<DataTable data={stores} rows=10 search=true>
  <Column id=store_key/>
  <Column id=store_type/>
  <Column id=assortment_name/>
  <Column id=competition_distance fmt='#,##0'/>
  <Column id=total_sales fmt='#,##0'/>
  <Column id=avg_open_day_sales fmt='#,##0'/>
  <Column id=promo_rate fmt='0.0%'/>
</DataTable>

<ScatterPlot data={stores} x=competition_distance y=avg_open_day_sales series=store_type title="Avg open-day sales vs competition distance"/>
