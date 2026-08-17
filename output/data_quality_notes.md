# Data Quality Notes

Checks run by `scripts/01_data_quality_checks.py` against `data/customers.csv` and `data/subscription_events.csv` before any metric is derived from the ledger.

**Result: ALL CHECKS PASSED**

## Checks

| Check | Result | Detail |
|---|---|---|
| No duplicate signup events per customer | ✅ Pass | 0 duplicate signup event(s) found. |
| No negative MRR values | ✅ Pass | 0 event row(s) with a negative mrr_before/mrr_after. |
| All event_dates within Jan 2023 - Dec 2024 | ✅ Pass | 0 event(s) outside the Jan 2023-Dec 2024 window. |
| At most one event per customer per calendar month | ✅ Pass | 0 customer-month(s) with more than one event (would need a tie-break rule for forward-fill). |
| No same-month signup+cancel | ✅ Pass | 0 customer(s) cancel in their signup month (zero active months, would need explicit handling). |
| Every event's customer_id exists in customers.csv | ✅ Pass | 0 event(s) reference a customer_id not in customers.csv. |

## Dataset summary

- Customers: **5,142**
- Events: **8,151**
  - `cancel`: 2,146
  - `downgrade`: 172
  - `signup`: 5,142
  - `upgrade`: 691
- Customers who cancelled at some point: **2,146** (41.7% of all signups)

## Conclusion

The ledger is clean: no duplicate signups, no negative MRR, no out-of-window dates, at most one event per customer per month, and no same-month signup+cancel edge case. This means the monthly snapshot in Step 2 can forward-fill directly from `subscription_events.csv` with a simple "last event on/before month M" rule — no de-duplication or tie-breaking logic needed.
