# Marketing Portfolio Planner

A multi-country Streamlit application generated from the original June 2026 marketing report.

## Features

- All countries from the original Excel report
- Country dropdown
- Separate planning assumptions per country
- Portfolio dashboard sorted by calculated leads, highest first
- Marketing budget, target FTD, and leads driver modes
- Potential conversion / deposit attempt rate
- Approval ratio
- CPL, PV per FTD, PSP fees, variable costs, and fixed costs
- Live CPA, ROI, net deposits, and net marketing profit
- 20-level approval sensitivity table
- CSV and JSON exports
- Optional password protection
- Optional Supabase persistence for saved shared online data

## Deploy to Streamlit Community Cloud

Upload these files and folders to the root of your GitHub repository:

- `app.py`
- `baseline_countries.json`
- `requirements.txt`
- `supabase_schema.sql`
- `.streamlit/config.toml`
- `.streamlit/secrets.toml.example`

Deploy using:

- Repository: `YOUR-GITHUB-USERNAME/YOUR-REPOSITORY`
- Branch: `main`
- Main file path: `app.py`

## Permanent online saving with Supabase

Without a database, Streamlit Cloud may erase local changes when the app restarts.

1. Create a free Supabase project.
2. Open **SQL Editor**.
3. Paste and run `supabase_schema.sql`.
4. In Supabase, open **Project Settings → API**.
5. Copy:
   - Project URL
   - anon/public API key
6. Open Streamlit Cloud:
   - Your app → Settings → Secrets
7. Paste:

```toml
SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
SUPABASE_KEY = "YOUR-ANON-KEY"
APP_PASSWORD = "optional-password"
```

8. Reboot the Streamlit app.
9. Use **Save current country** or **Save all countries**.

## Local run

```bash
python3 -m pip install -r requirements.txt
streamlit run app.py
```

Local changes are saved to `country_plans.local.json` when Supabase is not configured.


## Navigation fix

This build adds visible icon-based top navigation and explicit tab label styling.
