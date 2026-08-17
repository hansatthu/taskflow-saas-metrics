"""
Synthetic SaaS dataset generator — "TaskFlow" (fictional project-management SaaS)
Produces a Stripe-style event ledger so the analyst has to reconstruct
MRR, churn, NRR, LTV and CAC themselves (mirrors how real SaaS billing data looks).

Output files (in ./output):
  - customers.csv
  - subscription_events.csv
  - marketing_spend.csv
  - plans.csv
  - data_dictionary.md
"""

import numpy as np
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

rng = np.random.default_rng(42)

# ----------------------------------------------------------------------
# 1. CONFIG
# ----------------------------------------------------------------------
START_MONTH = date(2023, 1, 1)
N_MONTHS = 24
MONTHS = [START_MONTH + relativedelta(months=i) for i in range(N_MONTHS)]

PLANS = {
    "Free": 0,
    "Pro": 15,
    "Business": 49,
    "Enterprise": 199,
}

CHANNELS = ["Organic Search", "Paid Ads", "Referral", "Content Marketing", "Outbound Sales"]
CHANNEL_WEIGHTS = [0.34, 0.28, 0.15, 0.18, 0.05]

CHANNEL_INITIAL_PLAN_DIST = {
    "Organic Search":     {"Free": 0.45, "Pro": 0.45, "Business": 0.10, "Enterprise": 0.00},
    "Paid Ads":           {"Free": 0.55, "Pro": 0.40, "Business": 0.05, "Enterprise": 0.00},
    "Referral":           {"Free": 0.30, "Pro": 0.50, "Business": 0.20, "Enterprise": 0.00},
    "Content Marketing":  {"Free": 0.50, "Pro": 0.40, "Business": 0.10, "Enterprise": 0.00},
    "Outbound Sales":     {"Free": 0.00, "Pro": 0.05, "Business": 0.15, "Enterprise": 0.80},
}

CHANNEL_CHURN_MULT = {
    "Organic Search": 0.85, "Paid Ads": 1.45, "Referral": 0.70,
    "Content Marketing": 0.95, "Outbound Sales": 0.55,
}

PLAN_BASE_MONTHLY_CHURN = {"Free": 0.10, "Pro": 0.05, "Business": 0.035, "Enterprise": 0.015}

TARGET_CAC = {"Organic Search": 20, "Paid Ads": 120, "Referral": 10,
              "Content Marketing": 35, "Outbound Sales": 600}

REGIONS = ["North America", "Europe", "Asia Pacific", "Latin America"]
REGION_WEIGHTS = [0.42, 0.30, 0.20, 0.08]

PLAN_ORDER = ["Free", "Pro", "Business", "Enterprise"]

# ----------------------------------------------------------------------
# 2. SIGNUP SCHEDULE (growth curve + seasonality + noise)
# ----------------------------------------------------------------------
def monthly_signup_target(i, m):
    base = 80 + i * 13                       # steady growth month over month
    if m.month in (12, 1):
        base *= 0.7                          # holiday dip
    if m.month in (7, 8):
        base *= 0.85                         # summer dip
    noise = rng.normal(1.0, 0.08)
    return max(20, int(base * noise))

customers = []
cust_counter = 1

for i, m in enumerate(MONTHS):
    n_signups = monthly_signup_target(i, m)
    channels = rng.choice(CHANNELS, size=n_signups, p=CHANNEL_WEIGHTS)
    for ch in channels:
        cid = f"CUST-{cust_counter:05d}"
        cust_counter += 1
        dist = CHANNEL_INITIAL_PLAN_DIST[ch]
        plan = rng.choice(list(dist.keys()), p=list(dist.values()))
        region = rng.choice(REGIONS, p=REGION_WEIGHTS)
        if plan == "Enterprise":
            company_size = int(rng.integers(200, 5000))
        elif plan == "Business":
            company_size = int(rng.integers(10, 250))
        elif plan == "Pro":
            company_size = int(rng.integers(2, 50))
        else:
            company_size = int(rng.integers(1, 20))
        signup_day = rng.integers(1, 28)
        signup_date = date(m.year, m.month, signup_day)
        customers.append({
            "customer_id": cid,
            "signup_date": signup_date,
            "acquisition_channel": ch,
            "region": region,
            "company_size": company_size,
            "initial_plan": plan,
        })

customers_df = pd.DataFrame(customers)
print(f"Generated {len(customers_df)} customers")

# ----------------------------------------------------------------------
# 3. SIMULATE MONTHLY LIFECYCLE PER CUSTOMER -> EVENT LEDGER
# ----------------------------------------------------------------------
events = []
event_counter = 1
END_DATE = MONTHS[-1] + relativedelta(months=1) - relativedelta(days=1)  # end of last month

def add_event(cid, edate, etype, plan_before, plan_after):
    global event_counter
    events.append({
        "event_id": f"EVT-{event_counter:06d}",
        "customer_id": cid,
        "event_date": edate,
        "event_type": etype,
        "plan_before": plan_before,
        "plan_after": plan_after,
        "mrr_before": PLANS.get(plan_before, 0) if plan_before else 0,
        "mrr_after": PLANS.get(plan_after, 0) if plan_after else 0,
    })
    event_counter += 1

for row in customers_df.itertuples():
    cid = row.customer_id
    ch = row.acquisition_channel
    plan = row.initial_plan
    signup_date = row.signup_date

    add_event(cid, signup_date, "signup", None, plan)

    # simulate month by month from signup until END_DATE or churn
    cursor = date(signup_date.year, signup_date.month, 1) + relativedelta(months=1)
    tenure_months = 0
    churned = False

    while cursor <= END_DATE and not churned:
        tenure_months += 1

        # tenure-based churn multiplier (early-life churn is higher, loyal survivors churn less)
        if tenure_months <= 2:
            tenure_mult = 1.6
        elif tenure_months <= 4:
            tenure_mult = 1.2
        elif tenure_months <= 12:
            tenure_mult = 1.0
        else:
            tenure_mult = 0.75

        churn_p = PLAN_BASE_MONTHLY_CHURN[plan] * CHANNEL_CHURN_MULT[ch] * tenure_mult
        churn_p = min(churn_p, 0.6)

        event_day = int(rng.integers(1, 28))
        event_date = date(cursor.year, cursor.month, event_day)

        if rng.random() < churn_p:
            add_event(cid, event_date, "cancel", plan, "Cancelled")
            churned = True
            break

        # upgrade / downgrade logic (mutually exclusive per month)
        idx = PLAN_ORDER.index(plan)
        upgrade_p, downgrade_p = 0.0, 0.0

        if plan == "Free":
            upgrade_p = 0.07 if tenure_months <= 3 else 0.025
            if ch in ("Referral", "Outbound Sales"):
                upgrade_p *= 1.4
        elif plan == "Pro":
            upgrade_p = 0.02
            downgrade_p = 0.008
        elif plan == "Business":
            upgrade_p = 0.006
            downgrade_p = 0.010
        elif plan == "Enterprise":
            downgrade_p = 0.003

        roll = rng.random()
        if roll < upgrade_p and idx < len(PLAN_ORDER) - 1:
            new_plan = PLAN_ORDER[idx + 1]
            add_event(cid, event_date, "upgrade", plan, new_plan)
            plan = new_plan
        elif roll < upgrade_p + downgrade_p and idx > 0:
            new_plan = PLAN_ORDER[idx - 1]
            add_event(cid, event_date, "downgrade", plan, new_plan)
            plan = new_plan
        # else: no event this month (silent retention)

        cursor += relativedelta(months=1)

events_df = pd.DataFrame(events).sort_values(["event_date", "customer_id"]).reset_index(drop=True)
print(f"Generated {len(events_df)} events")

# ----------------------------------------------------------------------
# 4. MARKETING SPEND (derived from actual new customers per channel per month, + noise)
# ----------------------------------------------------------------------
customers_df["signup_month"] = pd.to_datetime(customers_df["signup_date"]).values.astype("datetime64[M]")
spend_rows = []
grp = customers_df.groupby(["signup_month", "acquisition_channel"]).size().reset_index(name="new_customers")

for row in grp.itertuples():
    cac_target = TARGET_CAC[row.acquisition_channel]
    noise = rng.normal(1.0, 0.12)
    spend = round(row.new_customers * cac_target * max(noise, 0.5), 2)
    spend_rows.append({
        "month": pd.Timestamp(row.signup_month).strftime("%Y-%m-01"),
        "channel": row.acquisition_channel,
        "spend": spend,
    })

spend_df = pd.DataFrame(spend_rows).sort_values(["month", "channel"]).reset_index(drop=True)

# ----------------------------------------------------------------------
# 5. PLANS REFERENCE TABLE
# ----------------------------------------------------------------------
plans_df = pd.DataFrame([{"plan": k, "monthly_price_usd": v} for k, v in PLANS.items()])

# ----------------------------------------------------------------------
# 6. SAVE
# ----------------------------------------------------------------------
import os
os.makedirs("output", exist_ok=True)

customers_out = customers_df.drop(columns=["signup_month"]).copy()
customers_out.to_csv("output/customers.csv", index=False)
events_df.to_csv("output/subscription_events.csv", index=False)
spend_df.to_csv("output/marketing_spend.csv", index=False)
plans_df.to_csv("output/plans.csv", index=False)

print("\nSaved files:")
print(f"  customers.csv          {len(customers_out):,} rows")
print(f"  subscription_events.csv {len(events_df):,} rows")
print(f"  marketing_spend.csv     {len(spend_df):,} rows")
print(f"  plans.csv               {len(plans_df):,} rows")

# quick sanity check: active MRR at end of period
active = events_df.sort_values("event_date").groupby("customer_id").last()
active_paid = active[(active["plan_after"] != "Cancelled") & (active["plan_after"] != "Free")]
end_mrr = active_paid["mrr_after"].sum()
print(f"\nSanity check — approx. active paid MRR at end of period: ${end_mrr:,.0f}")
print(f"Approx. active paying customers: {len(active_paid):,}")
