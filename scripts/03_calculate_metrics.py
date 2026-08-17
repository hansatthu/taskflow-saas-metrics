"""
Step 3 — Core metrics.

Reads output/monthly_snapshot.csv (Step 2) plus the raw event ledger and
reference tables, and writes eight metric files to output/:

  mrr_by_month.csv        total MRR per month
  mrr_waterfall.csv       New / Expansion / Contraction / Churned MRR per month
  churn_rate_by_month.csv logo churn % and revenue churn %
  nrr_by_month.csv        Net Revenue Retention %
  cac_by_channel.csv      marketing spend / new customers, per channel per month
  ltv_by_plan.csv         LTV = (ARPU x gross margin assumption) / churn rate
  ltv_cac_by_channel.csv  LTV:CAC ratio per channel
  cohort_retention.csv    % of each signup-month cohort still active N months later

Gross margin assumption: 80% (stated explicitly here — it is not in the
raw data). See output/business_insights.md for why this figure was chosen.
"""

import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

DATA = "data"
OUTPUT = "output"
GROSS_MARGIN = 0.80

customers = pd.read_csv(f"{DATA}/customers.csv", parse_dates=["signup_date"])
events = pd.read_csv(f"{DATA}/subscription_events.csv", parse_dates=["event_date"])
marketing = pd.read_csv(f"{DATA}/marketing_spend.csv", parse_dates=["month"])
snapshot = pd.read_csv(f"{OUTPUT}/monthly_snapshot.csv", parse_dates=["month"])

customers["signup_month"] = customers.signup_date.values.astype("datetime64[M]")
events["event_month"] = events.event_date.values.astype("datetime64[M]")

ALL_MONTHS = pd.date_range("2023-01-01", "2024-12-01", freq="MS")

# ----------------------------------------------------------------------
# 1. mrr_by_month.csv
# ----------------------------------------------------------------------
mrr_by_month = (
    snapshot.groupby("month")["mrr"].sum().reindex(ALL_MONTHS, fill_value=0)
)
mrr_by_month = mrr_by_month.rename_axis("month").reset_index(name="mrr")
mrr_by_month.to_csv(f"{OUTPUT}/mrr_by_month.csv", index=False)

# ----------------------------------------------------------------------
# 2. mrr_waterfall.csv — New / Expansion / Contraction / Churned MRR
# ----------------------------------------------------------------------
delta = events.mrr_after - events.mrr_before
waterfall_rows = []
for month in ALL_MONTHS:
    month_events = events[events.event_month == month]

    new_mrr = month_events.loc[month_events.event_type == "signup", "mrr_after"].sum()

    up = month_events[month_events.event_type == "upgrade"]
    expansion_mrr = (up.mrr_after - up.mrr_before).clip(lower=0).sum()

    down = month_events[month_events.event_type == "downgrade"]
    contraction_mrr = (down.mrr_before - down.mrr_after).clip(lower=0).sum()

    can = month_events[month_events.event_type == "cancel"]
    churned_mrr = can.mrr_before.sum()

    prev_month = month - pd.DateOffset(months=1)
    starting_mrr = (
        mrr_by_month.loc[mrr_by_month.month == prev_month, "mrr"].sum()
        if (mrr_by_month.month == prev_month).any()
        else 0
    )
    ending_mrr = mrr_by_month.loc[mrr_by_month.month == month, "mrr"].sum()

    waterfall_rows.append(
        {
            "month": month,
            "starting_mrr": starting_mrr,
            "new_mrr": new_mrr,
            "expansion_mrr": expansion_mrr,
            "contraction_mrr": -contraction_mrr,
            "churned_mrr": -churned_mrr,
            "ending_mrr": ending_mrr,
        }
    )

mrr_waterfall = pd.DataFrame(waterfall_rows)
mrr_waterfall.to_csv(f"{OUTPUT}/mrr_waterfall.csv", index=False)

# ----------------------------------------------------------------------
# 3. churn_rate_by_month.csv — logo churn % and revenue churn %
# ----------------------------------------------------------------------
active_start = snapshot.groupby("month").agg(
    active_customers_soM=("customer_id", "nunique"), mrr_soM=("mrr", "sum")
)
active_start.index = active_start.index + pd.DateOffset(months=1)

churn_rows = []
for month in ALL_MONTHS:
    can = events[(events.event_type == "cancel") & (events.event_month == month)]
    churned_logos = can.customer_id.nunique()
    churned_mrr = can.mrr_before.sum()

    prior = active_start.loc[month] if month in active_start.index else None
    active_soM = int(prior.active_customers_soM) if prior is not None else 0
    mrr_soM = float(prior.mrr_soM) if prior is not None else 0.0

    logo_churn_rate = churned_logos / active_soM if active_soM else np.nan
    revenue_churn_rate = churned_mrr / mrr_soM if mrr_soM else np.nan

    churn_rows.append(
        {
            "month": month,
            "active_customers_start_of_month": active_soM,
            "churned_customers": churned_logos,
            "logo_churn_rate": logo_churn_rate,
            "mrr_start_of_month": mrr_soM,
            "churned_mrr": churned_mrr,
            "revenue_churn_rate": revenue_churn_rate,
        }
    )

churn_rate_by_month = pd.DataFrame(churn_rows)
churn_rate_by_month.to_csv(f"{OUTPUT}/churn_rate_by_month.csv", index=False)

# ----------------------------------------------------------------------
# 4. nrr_by_month.csv — existing customers only, excludes New MRR
# ----------------------------------------------------------------------
nrr_rows = []
for _, w in mrr_waterfall.iterrows():
    if w.starting_mrr:
        nrr = (
            w.starting_mrr + w.expansion_mrr + w.contraction_mrr + w.churned_mrr
        ) / w.starting_mrr
    else:
        nrr = np.nan
    nrr_rows.append({"month": w.month, "starting_mrr": w.starting_mrr, "nrr": nrr})

nrr_by_month = pd.DataFrame(nrr_rows)
nrr_by_month.to_csv(f"{OUTPUT}/nrr_by_month.csv", index=False)

# ----------------------------------------------------------------------
# 5. cac_by_channel.csv — spend / new customers, per channel per month
# ----------------------------------------------------------------------
new_customers = (
    customers.groupby(["signup_month", "acquisition_channel"])
    .size()
    .rename("new_customers")
    .reset_index()
    .rename(columns={"signup_month": "month", "acquisition_channel": "channel"})
)

cac_by_channel = marketing.merge(new_customers, on=["month", "channel"], how="left")
cac_by_channel["new_customers"] = cac_by_channel.new_customers.fillna(0).astype(int)
cac_by_channel["cac"] = cac_by_channel.spend / cac_by_channel.new_customers.replace(
    0, np.nan
)
cac_by_channel = cac_by_channel.sort_values(["channel", "month"])
cac_by_channel.to_csv(f"{OUTPUT}/cac_by_channel.csv", index=False)

# ----------------------------------------------------------------------
# 6. ltv_by_plan.csv — LTV = (ARPU x gross margin) / monthly churn rate
# ----------------------------------------------------------------------
last_month = ALL_MONTHS.max()
current_state = snapshot[snapshot.month == last_month]

overall_monthly_churn = churn_rate_by_month.logo_churn_rate.mean(skipna=True)

plan_price = pd.read_csv(f"{DATA}/plans.csv").set_index("plan").monthly_price_usd

ltv_rows = []
for plan, arpu in plan_price.items():
    if plan == "Free":
        ltv = 0.0
    else:
        ltv = (arpu * GROSS_MARGIN) / overall_monthly_churn
    active_now = int((current_state.plan == plan).sum())
    ltv_rows.append(
        {
            "plan": plan,
            "arpu_usd": arpu,
            "gross_margin_assumption": GROSS_MARGIN,
            "monthly_churn_rate_used": overall_monthly_churn,
            "ltv_usd": ltv,
            "active_customers_dec_2024": active_now,
        }
    )

ltv_by_plan = pd.DataFrame(ltv_rows)
ltv_by_plan.to_csv(f"{OUTPUT}/ltv_by_plan.csv", index=False)

# ----------------------------------------------------------------------
# 7. ltv_cac_by_channel.csv
# ----------------------------------------------------------------------
# Blended ARPU per channel among that channel's currently-active paying
# customers, so each channel's LTV reflects the plan mix it actually brings.
# monthly_snapshot.csv already carries acquisition_channel (Step 2 output).
paying_active = current_state[current_state.plan != "Free"]
arpu_by_channel = paying_active.groupby("acquisition_channel")["mrr"].mean()

channel_ltv = (arpu_by_channel * GROSS_MARGIN) / overall_monthly_churn
channel_ltv.name = "ltv_usd"

total_spend_by_channel = marketing.groupby("channel").spend.sum()
total_new_customers_by_channel = new_customers.groupby("channel").new_customers.sum()
blended_cac = total_spend_by_channel / total_new_customers_by_channel
blended_cac.name = "cac_usd"

ltv_cac = pd.concat([channel_ltv, blended_cac], axis=1).rename_axis(
    "acquisition_channel"
).reset_index()
ltv_cac["ltv_cac_ratio"] = ltv_cac.ltv_usd / ltv_cac.cac_usd
ltv_cac = ltv_cac.sort_values("ltv_cac_ratio", ascending=False)
ltv_cac.to_csv(f"{OUTPUT}/ltv_cac_by_channel.csv", index=False)

# ----------------------------------------------------------------------
# 8. cohort_retention.csv — % of each signup cohort active N months later
# ----------------------------------------------------------------------
cohort_size = customers.groupby("signup_month").size().rename("cohort_size")

snap_with_cohort = snapshot.merge(
    customers[["customer_id", "signup_month"]], on="customer_id", how="left"
)
snap_with_cohort["months_since_signup"] = (
    (snap_with_cohort.month.dt.year - snap_with_cohort.signup_month.dt.year) * 12
    + (snap_with_cohort.month.dt.month - snap_with_cohort.signup_month.dt.month)
)

active_counts = (
    snap_with_cohort.groupby(["signup_month", "months_since_signup"])["customer_id"]
    .nunique()
    .rename("active_customers")
    .reset_index()
)

cohort_retention = active_counts.merge(cohort_size, on="signup_month", how="left")
cohort_retention["retention_rate"] = (
    cohort_retention.active_customers / cohort_retention.cohort_size
)
cohort_retention = cohort_retention.rename(columns={"signup_month": "cohort_month"})
cohort_retention = cohort_retention.sort_values(
    ["cohort_month", "months_since_signup"]
)
cohort_retention.to_csv(f"{OUTPUT}/cohort_retention.csv", index=False)

# ----------------------------------------------------------------------
# Console summary
# ----------------------------------------------------------------------
print(f"Gross margin assumption used for LTV: {GROSS_MARGIN:.0%}")
print(f"Overall average monthly logo churn rate: {overall_monthly_churn:.2%}")
print()
print("mrr_by_month.csv        ", mrr_by_month.shape)
print("mrr_waterfall.csv       ", mrr_waterfall.shape)
print("churn_rate_by_month.csv ", churn_rate_by_month.shape)
print("nrr_by_month.csv        ", nrr_by_month.shape)
print("cac_by_channel.csv      ", cac_by_channel.shape)
print("ltv_by_plan.csv         ", ltv_by_plan.shape)
print("ltv_cac_by_channel.csv  ", ltv_cac.shape)
print("cohort_retention.csv    ", cohort_retention.shape)
print()
print("MRR: Jan 2023 =", int(mrr_by_month.iloc[0].mrr), "-> Dec 2024 =", int(mrr_by_month.iloc[-1].mrr))
print()
print("LTV:CAC by channel:")
print(ltv_cac.to_string(index=False))
