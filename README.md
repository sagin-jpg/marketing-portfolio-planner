# FTD Target Control Center

A Power BI–style Streamlit application for target FTD planning, daily actual uploads, and target-vs-reality gap control.

## Core workflow

1. Create a monthly target plan.
2. Enter target FTDs by country.
3. Save the plan.
4. Upload daily actual files.
5. Review Executive Overview and Gap Analysis.
6. Drill into individual countries.
7. Compare saved plans.

## Supported actual upload formats

`.xlsx`, `.xls`, or `.csv`

Recommended columns:

- Country
- Leads
- FTDs
- Marketing Cost
- NDP

Optional:

- Date
- Conversion Rate
- CPL
- CPA
- ROI

The original report structure is also supported:
`Row Labels, Leads, FTD #, CR %, COST, CPL, Avg CPA, ROI, NDP$`

## Deploy

Upload all files to GitHub, then deploy with Streamlit Cloud using:

- Branch: `main`
- Main file path: `app.py`

## Permanent saving

Run `supabase_schema.sql` in Supabase SQL Editor.

Then add Streamlit secrets:

```toml
SUPABASE_URL="https://YOUR-PROJECT.supabase.co"
SUPABASE_KEY="YOUR-ANON-KEY"
APP_PASSWORD="optional-password"
```


## CPA funnel linkage

CPA is calculated as:

`CPA = CPL / (Potential Conversion × Approval Ratio)`

Changing CPL, potential conversion, or approval ratio updates CPA, required leads, marketing spend, ROI, and target profit.
