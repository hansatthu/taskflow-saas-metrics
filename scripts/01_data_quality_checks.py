"""
Step 1 — Data understanding & cleaning.

Runs sanity checks on the raw event ledger before any metric is derived
from it, and writes the findings to output/data_quality_notes.md.

Checks:
  - Exactly one signup event per customer, no duplicates
  - No negative MRR values (mrr_before / mrr_after)
  - All event_dates fall within the dataset's stated window
  - No more than one event per customer in the same calendar month
    (would break the "last event on/before month M" forward-fill rule)
  - No customer cancels in the same month they signed up
    (would leave them with zero active months)
  - Every customer referenced in subscription_events exists in customers.csv
"""

import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

DATA = "data"
OUTPUT = "output"
WINDOW_START = pd.Timestamp("2023-01-01")
WINDOW_END = pd.Timestamp("2024-12-31")

customers = pd.read_csv(f"{DATA}/customers.csv", parse_dates=["signup_date"])
events = pd.read_csv(f"{DATA}/subscription_events.csv", parse_dates=["event_date"])

checks = []


def check(name, passed, detail):
    checks.append({"name": name, "passed": passed, "detail": detail})


# 1. Duplicate signups
signups = events[events.event_type == "signup"]
dup_signups = int(signups.customer_id.duplicated().sum())
check(
    "No duplicate signup events per customer",
    dup_signups == 0,
    f"{dup_signups} duplicate signup event(s) found.",
)

# 2. Negative MRR
neg_mrr = int(((events.mrr_before < 0) | (events.mrr_after < 0)).sum())
check(
    "No negative MRR values",
    neg_mrr == 0,
    f"{neg_mrr} event row(s) with a negative mrr_before/mrr_after.",
)

# 3. Event dates within window
out_of_window = int(
    ((events.event_date < WINDOW_START) | (events.event_date > WINDOW_END)).sum()
)
check(
    "All event_dates within Jan 2023 - Dec 2024",
    out_of_window == 0,
    f"{out_of_window} event(s) outside the Jan 2023-Dec 2024 window.",
)

# 4. Multiple events for the same customer in the same month
events["event_month"] = events.event_date.values.astype("datetime64[M]")
per_month = events.groupby(["customer_id", "event_month"]).size()
multi_event_months = int((per_month > 1).sum())
check(
    "At most one event per customer per calendar month",
    multi_event_months == 0,
    f"{multi_event_months} customer-month(s) with more than one event "
    "(would need a tie-break rule for forward-fill).",
)

# 5. Cancel in the same month as signup
cancels = events[events.event_type == "cancel"][["customer_id", "event_date"]]
cancels = cancels.rename(columns={"event_date": "cancel_date"})
merged = signups[["customer_id", "event_date"]].rename(
    columns={"event_date": "signup_date"}
).merge(cancels, on="customer_id", how="inner")
same_month_cancel = int(
    (
        merged.signup_date.values.astype("datetime64[M]")
        == merged.cancel_date.values.astype("datetime64[M]")
    ).sum()
)
check(
    "No same-month signup+cancel",
    same_month_cancel == 0,
    f"{same_month_cancel} customer(s) cancel in their signup month "
    "(zero active months, would need explicit handling).",
)

# 6. Referential integrity
orphan_events = int((~events.customer_id.isin(customers.customer_id)).sum())
check(
    "Every event's customer_id exists in customers.csv",
    orphan_events == 0,
    f"{orphan_events} event(s) reference a customer_id not in customers.csv.",
)

# ---- Summary stats worth recording alongside the pass/fail checks ----
n_customers = len(customers)
n_events = len(events)
event_type_counts = events.event_type.value_counts().to_dict()
n_cancelled_ever = int(customers.customer_id.isin(cancels.customer_id).sum())

all_passed = all(c["passed"] for c in checks)

lines = []
lines.append("# Data Quality Notes")
lines.append("")
lines.append(
    "Checks run by `scripts/01_data_quality_checks.py` against "
    "`data/customers.csv` and `data/subscription_events.csv` before any "
    "metric is derived from the ledger."
)
lines.append("")
lines.append(f"**Result: {'ALL CHECKS PASSED' if all_passed else 'ISSUES FOUND'}**")
lines.append("")
lines.append("## Checks")
lines.append("")
lines.append("| Check | Result | Detail |")
lines.append("|---|---|---|")
for c in checks:
    status = "✅ Pass" if c["passed"] else "❌ Fail"
    lines.append(f"| {c['name']} | {status} | {c['detail']} |")
lines.append("")
lines.append("## Dataset summary")
lines.append("")
lines.append(f"- Customers: **{n_customers:,}**")
lines.append(f"- Events: **{n_events:,}**")
for et, cnt in sorted(event_type_counts.items()):
    lines.append(f"  - `{et}`: {cnt:,}")
lines.append(f"- Customers who cancelled at some point: **{n_cancelled_ever:,}** "
             f"({n_cancelled_ever / n_customers:.1%} of all signups)")
lines.append("")
lines.append("## Conclusion")
lines.append("")
if all_passed:
    lines.append(
        "The ledger is clean: no duplicate signups, no negative MRR, no "
        "out-of-window dates, at most one event per customer per month, "
        "and no same-month signup+cancel edge case. This means the "
        "monthly snapshot in Step 2 can forward-fill directly from "
        "`subscription_events.csv` with a simple \"last event on/before "
        "month M\" rule — no de-duplication or tie-breaking logic needed."
    )
else:
    lines.append(
        "One or more checks failed — resolve these before trusting any "
        "downstream metric. See the ❌ rows above for what to fix."
    )

with open(f"{OUTPUT}/data_quality_notes.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print("\n".join(lines))
