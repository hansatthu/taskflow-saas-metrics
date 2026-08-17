# TaskFlow — SaaS Metrics Analysis

**MRR · Churn · NRR · LTV:CAC — reconstructed from a raw billing event ledger**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-2.x-150458?logo=pandas&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-1.24%2B-013243?logo=numpy&logoColor=white)
![Status](https://img.shields.io/badge/status-in%20progress-yellow)
![License](https://img.shields.io/badge/license-portfolio--project-lightgrey)

Personal ITBA portfolio project. TaskFlow is a **fictional** project-management
SaaS with 24 months of synthetic subscription data (Jan 2023 – Dec 2024),
shaped like a real Stripe/billing export. The goal is to reconstruct core
SaaS financial metrics from a raw event ledger — no metric is handed to you
pre-computed — and turn them into business recommendations, the same
workflow a Business Analyst runs on real billing data.

---

## Table of contents

- [Business questions](#business-questions)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [Data model](#data-model)
- [Repository structure](#repository-structure)
- [Pipeline / build plan](#pipeline--build-plan)
- [Key formulas](#key-formulas-reference)
- [Getting started](#getting-started)
- [Status](#status)
- [Known limitations](#known-limitations)

---

## Business questions

This project must produce a defensible answer to each of these:

1. **Health** — Is TaskFlow growing in a healthy way, or leaking revenue?
2. **Channel quality** — Which acquisition channel brings the best-quality customers (highest LTV:CAC)?
3. **Strategy** — Should the company prioritize acquisition (new customers) or retention (reducing churn) next quarter?

---

## Tech stack

| Layer | Tool | Purpose |
|---|---|---|
| Language | **Python 3.10+** | Data generation, transformation, metric calculations |
| Data wrangling | **pandas**, **NumPy** | Forward-fill snapshots, groupby aggregations, waterfall/cohort logic |
| Dates | **python-dateutil** | Month-boundary arithmetic (`relativedelta`) |
| Storage | **CSV** (flat files) | Event ledger + dimension tables — mirrors a raw billing export |
| Dashboard | **Streamlit + Plotly** *(or Power BI / Tableau Public)* | Interactive Growth / Retention / Unit Economics views |
| Docs | **Markdown** | Data dictionary, data-quality notes, business insights |

> The dashboard track is a choice, not a fixed dependency — build it in
> whichever of Streamlit/Plotly, Power BI, or Tableau Public best fits how
> you want to present it. `requirements.txt` includes the Python track.

---

## Architecture

End-to-end flow from raw ledger to business recommendation:

```mermaid
flowchart LR
    subgraph Raw["📥 Raw Data (data/)"]
        A1[customers.csv]
        A2[subscription_events.csv]
        A3[marketing_spend.csv]
        A4[plans.csv]
    end

    subgraph Pipeline["⚙️ Processing (scripts/)"]
        B0[00_generate_data.py]
        B1[01_build_monthly_snapshot.py]
        B2[02_calculate_metrics.py]
    end

    subgraph Outputs["📊 Metrics (output/)"]
        C1[monthly_snapshot.csv]
        C2[mrr_by_month.csv]
        C3[mrr_waterfall.csv]
        C4[churn_rate_by_month.csv]
        C5[nrr_by_month.csv]
        C6[cac_by_channel.csv]
        C7[ltv_cac_by_channel.csv]
        C8[cohort_retention.csv]
    end

    D[📈 Dashboard\nGrowth · Retention · Unit Economics]
    E[📝 business_insights.md\nFinding → So what → Recommendation]

    B0 -.generates.-> A1 & A2 & A3 & A4
    A1 & A2 --> B1 --> C1
    C1 --> B2
    A3 & A4 --> B2
    B2 --> C2 & C3 & C4 & C5 & C6 & C7 & C8
    C2 & C3 & C4 & C5 & C6 & C7 & C8 --> D
    D --> E
```

---

## Data model

The event ledger is the **source of truth** — MRR, churn, and NRR are all
derived from it, never read off a pre-built column.

```mermaid
erDiagram
    CUSTOMERS ||--o{ SUBSCRIPTION_EVENTS : "has events"
    CUSTOMERS }o--|| PLANS : "initial_plan"
    SUBSCRIPTION_EVENTS }o--|| PLANS : "plan_before / plan_after"
    CUSTOMERS }o--|| MARKETING_SPEND : "acquisition_channel + signup month"

    CUSTOMERS {
        string customer_id PK
        date signup_date
        string acquisition_channel
        string region
        int company_size
        string initial_plan
    }
    SUBSCRIPTION_EVENTS {
        string event_id PK
        string customer_id FK
        date event_date
        string event_type "signup upgrade downgrade cancel"
        string plan_before
        string plan_after
        number mrr_before
        number mrr_after
    }
    MARKETING_SPEND {
        date month
        string channel
        number spend
    }
    PLANS {
        string plan PK
        number monthly_price_usd
    }
```

A customer's **state in any given month** = their last event on or before
that month (forward-filled).

---

## Repository structure

```
taskflow-saas-metrics/
├── README.md                        you are here
├── requirements.txt                  Python dependencies
├── data/
│   ├── customers.csv                 customer dimension table        (5,142 rows)
│   ├── subscription_events.csv       event ledger — source of truth  (8,151 rows)
│   ├── marketing_spend.csv           monthly spend by channel        (120 rows)
│   ├── plans.csv                     plan pricing reference          (4 rows)
│   └── data_dictionary.md            full schema + known limitations
├── scripts/
│   ├── 00_generate_data.py           dataset generator (seeded, reproducible)   ✅ done
│   ├── 01_build_monthly_snapshot.py  forward-fills plan/MRR per customer/month  ⬜ todo
│   └── 02_calculate_metrics.py       computes all metric CSVs below             ⬜ todo
├── output/                           analysis results land here (CSVs, notes)
│   ├── data_quality_notes.md
│   ├── monthly_snapshot.csv
│   ├── mrr_by_month.csv
│   ├── mrr_waterfall.csv
│   ├── churn_rate_by_month.csv
│   ├── nrr_by_month.csv
│   ├── cac_by_channel.csv
│   ├── ltv_by_plan.csv
│   ├── ltv_cac_by_channel.csv
│   ├── cohort_retention.csv
│   └── business_insights.md
└── dashboard/                        final dashboard file(s) / screenshots
```

---

## Pipeline / build plan

Run in order — each step depends on the previous step's output.

```mermaid
flowchart TD
    S1[Step 1 · Data understanding & cleaning\nsanity-check the event ledger] --> S2
    S2[Step 2 · Monthly customer snapshot\nforward-fill plan/MRR per customer] --> S3
    S3[Step 3 · Core metrics\nMRR, churn, NRR, CAC, LTV, cohorts] --> S4
    S4[Step 4 · Dashboard\nGrowth · Retention · Unit Economics] --> S5
    S5[Step 5 · Insights & recommendations\nanswer the 3 business questions] --> S6
    S6[Step 6 · Limitations\ndocument assumptions & gaps]
```

### Step 1 — Data understanding & cleaning
- Read `data/data_dictionary.md` fully before writing any code.
- Sanity-check the event ledger: no duplicate signups per customer, no
  negative MRR values, all event_dates within Jan 2023–Dec 2024.
- Write findings to `output/data_quality_notes.md`.

### Step 2 — Build the monthly customer snapshot
- Script: `scripts/01_build_monthly_snapshot.py`
- For every customer, forward-fill their plan/MRR state across every
  month from signup to Dec 2024 (or their cancel date) using the event
  ledger in `subscription_events.csv`.
- Output: `output/monthly_snapshot.csv` — one row per customer per
  active month, columns: `customer_id, month, plan, mrr, acquisition_channel`.
- Sanity check: total active paying customers in the last month should
  be close to **~2,162** (printed by the original generator run).

### Step 3 — Core metrics
- Script: `scripts/02_calculate_metrics.py`
- Compute, save each to its own CSV in `output/`:

| File | Contents |
|---|---|
| `mrr_by_month.csv` | Total MRR per month |
| `mrr_waterfall.csv` | New / Expansion / Contraction / Churned MRR per month |
| `churn_rate_by_month.csv` | Logo churn % and revenue churn % |
| `nrr_by_month.csv` | Net Revenue Retention % |
| `cac_by_channel.csv` | `marketing_spend` / new customers, per channel per month |
| `ltv_by_plan.csv` | LTV = (ARPU × gross margin assumption) / churn rate — **state the gross margin assumption explicitly** (e.g. 80%), it's not in the data |
| `ltv_cac_by_channel.csv` | LTV:CAC ratio per channel |
| `cohort_retention.csv` | % of each signup-month cohort still active N months later |

### Step 4 — Dashboard
- Build in Power BI / Tableau Public / or a Python (Plotly/Streamlit) app.
- Save final file/screenshots into `dashboard/`.
- Three views: **Growth Overview**, **Retention Health**, **Unit Economics**
  (see full spec in the conversation this project came from).

### Step 5 — Insights & recommendations
- Write `output/business_insights.md`: Finding → So what → Recommendation,
  answering the [3 business questions](#business-questions) at the top of this file.

### Step 6 — Limitations
- Add to `output/business_insights.md`: no involuntary churn modeled,
  gross margin is an assumption, no macro/competitive effects.

---

## Key formulas reference

```
MRR                 = sum(active subscription monthly value)
Churn Rate (%)      = churned customers in month / active customers at start of month
NRR (%)             = (Starting MRR + Expansion − Contraction − Churned MRR) / Starting MRR
                       (existing customers only — excludes New MRR)
CAC                 = marketing spend / new customers acquired, per channel/month
LTV                 = (ARPU × gross margin %) / monthly churn rate
LTV:CAC ratio       = LTV / CAC   (healthy benchmark: > 3:1)
```

---

## Getting started

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Already done) Regenerate the synthetic dataset if needed — seeded & reproducible
python scripts/00_generate_data.py

# 3. Build the monthly customer snapshot
python scripts/01_build_monthly_snapshot.py

# 4. Compute all core metrics
python scripts/02_calculate_metrics.py

# 5. Launch the dashboard (if using the Streamlit track)
streamlit run dashboard/app.py
```

---

## Status

- [x] Dataset generated (`data/`)
- [ ] Step 1 — data quality notes
- [ ] Step 2 — monthly snapshot
- [ ] Step 3 — core metrics
- [ ] Step 4 — dashboard
- [ ] Step 5 — insights
- [ ] Step 6 — limitations

---

## Known limitations

Intentional gaps in the synthetic dataset — discuss these in the final write-up:

- No seat-based/usage-based pricing — flat MRR per plan only.
- No refunds, failed payments, or involuntary churn (all cancels are voluntary).
- No macro/competitive shocks — churn and growth are driven only by plan, channel, and tenure.
- Gross margin isn't in the data — an assumption must be stated to calculate LTV.
