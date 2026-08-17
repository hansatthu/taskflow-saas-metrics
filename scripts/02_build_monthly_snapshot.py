"""
Step 2 — Build the monthly customer snapshot.

For every customer, forward-fill their plan/MRR state across every month
from signup to Dec 2024 (or the month before they cancel), using the
event ledger in data/subscription_events.csv as the source of truth.

A customer's state in month M = the plan_after/mrr_after of their most
recent event with event_date <= end of month M.

Output: output/monthly_snapshot.csv
  one row per customer per active month
  columns: customer_id, month, plan, mrr, acquisition_channel
"""

import pandas as pd

DATA = "data"
OUTPUT = "output"
LAST_MONTH = pd.Timestamp("2024-12-01")

customers = pd.read_csv(f"{DATA}/customers.csv", parse_dates=["signup_date"])
events = pd.read_csv(f"{DATA}/subscription_events.csv", parse_dates=["event_date"])

customers["signup_month"] = customers.signup_date.values.astype("datetime64[M]")
events["event_month"] = events.event_date.values.astype("datetime64[M]")

# Data quality checks (Step 1) confirmed at most one event per customer per
# month, so no de-duplication is needed before treating event_month as the
# forward-fill key.
events = events.sort_values(["customer_id", "event_month"])

cancels = events[events.event_type == "cancel"][["customer_id", "event_month"]]
cancels = cancels.rename(columns={"event_month": "cancel_month"})

cust = customers.merge(cancels, on="customer_id", how="left")
# Active through the month *before* the cancel month; never cancelled ->
# active through the last month of the dataset.
cust["end_month"] = cust.cancel_month - pd.DateOffset(months=1)
cust["end_month"] = cust.end_month.fillna(LAST_MONTH)
cust["end_month"] = cust.end_month.clip(upper=LAST_MONTH)

# Step 1 confirmed no customer cancels in their signup month, so every
# customer has at least one active month.
assert (cust.end_month >= cust.signup_month).all(), (
    "found a customer whose end_month precedes their signup_month"
)

# One row per (customer_id, month) they were active.
grid = pd.concat(
    [
        pd.DataFrame(
            {
                "customer_id": r.customer_id,
                "month": pd.date_range(r.signup_month, r.end_month, freq="MS"),
            }
        )
        for r in cust.itertuples(index=False)
    ],
    ignore_index=True,
)
grid = grid.sort_values(["month", "customer_id"]).reset_index(drop=True)

events_sorted = events.sort_values(["event_month", "customer_id"])[
    ["customer_id", "event_month", "plan_after", "mrr_after"]
]

snapshot = pd.merge_asof(
    grid,
    events_sorted,
    left_on="month",
    right_on="event_month",
    by="customer_id",
    direction="backward",
)
snapshot = snapshot.rename(columns={"plan_after": "plan", "mrr_after": "mrr"})
snapshot = snapshot.merge(
    customers[["customer_id", "acquisition_channel"]], on="customer_id", how="left"
)
snapshot = snapshot[["customer_id", "month", "plan", "mrr", "acquisition_channel"]]
snapshot = snapshot.sort_values(["customer_id", "month"]).reset_index(drop=True)
snapshot["month"] = snapshot.month.dt.strftime("%Y-%m-01")

snapshot.to_csv(f"{OUTPUT}/monthly_snapshot.csv", index=False)

last_month_str = LAST_MONTH.strftime("%Y-%m-01")
active_last_month = (snapshot.month == last_month_str).sum()
paying_last_month = (
    (snapshot.month == last_month_str) & (snapshot.plan != "Free")
).sum()

print(f"monthly_snapshot.csv rows: {len(snapshot):,}")
print(f"customers active in {last_month_str}: {active_last_month:,}")
print(f"paying (non-Free) customers active in {last_month_str}: {paying_last_month:,}")
print("(README sanity check: ~2,162 active paying customers in the last month)")
