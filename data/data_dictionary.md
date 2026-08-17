# TaskFlow SaaS — Synthetic Dataset (Data Dictionary)

Fictional project-management SaaS ("TaskFlow"), 24 months of history
(Jan 2023 – Dec 2024). Built as an event ledger — the same shape real
billing systems (e.g. Stripe) produce — so you reconstruct MRR, churn,
NRR, LTV and CAC yourself rather than reading them off a pre-built table.

## Files

### 1. `customers.csv` (5,142 rows)
One row per customer.

| Column | Type | Description |
|---|---|---|
| customer_id | string | Unique ID, e.g. `CUST-00001` |
| signup_date | date | Date the account was created |
| acquisition_channel | string | Organic Search, Paid Ads, Referral, Content Marketing, Outbound Sales |
| region | string | North America, Europe, Asia Pacific, Latin America |
| company_size | int | Approx. employee count of the customer's company |
| initial_plan | string | Plan chosen at signup: Free, Pro, Business, Enterprise |

### 2. `subscription_events.csv` (8,151 rows)
Event ledger — every plan-level change for every customer. This is
your **source of truth**; MRR/churn/NRR must be derived from it.

| Column | Type | Description |
|---|---|---|
| event_id | string | Unique event ID |
| customer_id | string | Foreign key → customers.csv |
| event_date | date | Date the event occurred |
| event_type | string | `signup`, `upgrade`, `downgrade`, `cancel` |
| plan_before | string | Plan before the event (null for signup) |
| plan_after | string | Plan after the event (`Cancelled` for cancel events) |
| mrr_before | number | Monthly value of plan_before |
| mrr_after | number | Monthly value of plan_after |

A customer's **current state in any given month** = their last event
on or before that month.

### 3. `marketing_spend.csv` (120 rows)
Monthly spend by acquisition channel — needed to calculate CAC.

| Column | Type | Description |
|---|---|---|
| month | date | First day of the month |
| channel | string | Matches acquisition_channel in customers.csv |
| spend | number | USD spent that month on that channel |

### 4. `plans.csv` (4 rows)
Reference table of plan pricing.

| Column | Type | Description |
|---|---|---|
| plan | string | Free, Pro, Business, Enterprise |
| monthly_price_usd | number | 0, 15, 49, 199 |

## Suggested build order

1. **Reconstruct monthly MRR**: for each customer, forward-fill their
   plan/MRR state across months from `subscription_events.csv`, then
   sum by month.
2. **MRR waterfall**: classify each event by month into New / Expansion
   (upgrade) / Contraction (downgrade) / Churned MRR.
3. **Churn rate**: churned customers in month / active customers at
   start of month.
4. **NRR**: (Starting MRR + Expansion − Contraction − Churned) /
   Starting MRR, for existing customers only (exclude New MRR).
5. **CAC**: `marketing_spend` / new customers that month, by channel
   (join on customers.signup_date's month + acquisition_channel).
6. **LTV**: (ARPU × gross margin assumption, e.g. 80%) / monthly churn
   rate. Assume gross margin yourself and state it as an assumption.
7. **Cohort retention curve**: group customers by signup month, track
   % still active N months later.

## Known limitations (intentional — discuss these in your write-up)

- No seat-based/usage-based pricing — flat MRR per plan only.
- No refunds, failed payments, or involuntary churn (all cancels are
  voluntary).
- No macro/competitive shocks — churn and growth are driven only by
  plan, channel and tenure.
- Gross margin isn't in the data — you must state an assumption to
  calculate LTV.
