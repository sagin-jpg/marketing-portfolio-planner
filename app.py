
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

try:
    from supabase import create_client
except Exception:
    create_client = None

st.set_page_config(
    page_title="Marketing Portfolio Planner",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASELINE_PATH = Path(__file__).with_name("baseline_countries.json")
LOCAL_STORE_PATH = Path(__file__).with_name("country_plans.local.json")
TABLE_NAME = "marketing_country_plans"

DRIVERS = ["Marketing Budget", "Target FTDs", "Leads Purchased"]


def safe_div(a: float, b: float) -> float:
    return a / b if b not in (0, 0.0) and math.isfinite(b) else 0.0


def currency(x: float) -> str:
    return f"${x:,.2f}"


def integer(x: float) -> str:
    return f"{x:,.0f}"


def pct(x: float) -> str:
    return f"{x * 100:,.2f}%"


def multiple(x: float) -> str:
    return f"{x:,.2f}x"


@st.cache_data
def load_baseline() -> list[dict[str, Any]]:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def get_supabase():
    if create_client is None:
        return None
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception:
        return None


def load_plans() -> tuple[list[dict[str, Any]], str]:
    baseline = load_baseline()
    supabase = get_supabase()

    if supabase is not None:
        try:
            response = supabase.table(TABLE_NAME).select("country,payload").execute()
            rows = response.data or []
            saved = {row["country"]: row["payload"] for row in rows}
            merged = []
            for base in baseline:
                plan = dict(base)
                plan.update(saved.get(base["country"], {}))
                merged.append(plan)
            return merged, "Supabase"
        except Exception as exc:
            st.warning(f"Supabase is configured but could not be read: {exc}")

    if LOCAL_STORE_PATH.exists():
        try:
            saved_rows = json.loads(LOCAL_STORE_PATH.read_text(encoding="utf-8"))
            saved = {row["country"]: row for row in saved_rows}
            merged = []
            for base in baseline:
                plan = dict(base)
                plan.update(saved.get(base["country"], {}))
                merged.append(plan)
            return merged, "Local file"
        except Exception:
            pass

    return baseline, "Session only"


def save_plan(plan: dict[str, Any]) -> tuple[bool, str]:
    supabase = get_supabase()
    payload = {k: v for k, v in plan.items() if k != "country"}

    if supabase is not None:
        try:
            row = {
                "country": plan["country"],
                "payload": payload,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            supabase.table(TABLE_NAME).upsert(row, on_conflict="country").execute()
            return True, "Saved to Supabase"
        except Exception as exc:
            return False, f"Supabase save failed: {exc}"

    try:
        LOCAL_STORE_PATH.write_text(
            json.dumps(st.session_state.plans, indent=2),
            encoding="utf-8",
        )
        return True, "Saved locally"
    except Exception:
        return False, "This hosted session has no permanent database configured."


def save_all() -> tuple[int, list[str]]:
    ok_count = 0
    errors = []
    for plan in st.session_state.plans:
        ok, msg = save_plan(plan)
        if ok:
            ok_count += 1
        else:
            errors.append(f'{plan["country"]}: {msg}')
    return ok_count, errors


def calculate(plan: dict[str, Any]) -> dict[str, float]:
    driver = plan["driver"]
    driver_value = max(0.0, float(plan["driver_value"]))
    cpl = max(0.0, float(plan["cpl"]))
    potential = min(max(float(plan["potential_conversion"]), 0.0), 1.0)
    approval = min(max(float(plan["approval_ratio"]), 0.0), 1.0)
    pv = max(0.0, float(plan["pv_per_ftd"]))
    psp_fee = min(max(float(plan["psp_fee"]), 0.0), 1.0)
    variable_cost = max(0.0, float(plan["variable_cost_per_ftd"]))
    fixed_cost = max(0.0, float(plan["fixed_monthly_cost"]))

    conversion = potential * approval

    if driver == "Marketing Budget":
        spend = driver_value
        leads = safe_div(spend, cpl)
        attempts = leads * potential
        ftds = attempts * approval
    elif driver == "Target FTDs":
        ftds = driver_value
        attempts = safe_div(ftds, approval)
        leads = safe_div(attempts, potential)
        spend = leads * cpl
    else:
        leads = driver_value
        spend = leads * cpl
        attempts = leads * potential
        ftds = attempts * approval

    cpa = safe_div(spend, ftds)
    net_deposits = ftds * pv
    roi = safe_div(net_deposits, spend)
    psp_cost = net_deposits * psp_fee
    variable_total = ftds * variable_cost
    net_profit = net_deposits - spend - psp_cost - variable_total - fixed_cost
    profit_per_ftd = safe_div(net_profit, ftds)
    profit_margin = safe_div(net_profit, net_deposits)
    break_even_cpa = pv * (1 - psp_fee) - variable_cost
    break_even_cpl = break_even_cpa * conversion
    max_profitable_spend = net_deposits - psp_cost - variable_total - fixed_cost
    budget_headroom = max_profitable_spend - spend

    return {
        "ftd_conversion": conversion,
        "marketing_spend": spend,
        "leads": leads,
        "deposit_attempts": attempts,
        "ftds": ftds,
        "cpa": cpa,
        "net_deposits": net_deposits,
        "roi": roi,
        "psp_cost": psp_cost,
        "variable_cost_total": variable_total,
        "net_profit": net_profit,
        "profit_per_ftd": profit_per_ftd,
        "profit_margin": profit_margin,
        "break_even_cpa": break_even_cpa,
        "break_even_cpl": break_even_cpl,
        "max_profitable_spend": max_profitable_spend,
        "budget_headroom": budget_headroom,
    }


def password_gate() -> None:
    password = st.secrets.get("APP_PASSWORD", "")
    if not password:
        return

    if st.session_state.get("authenticated"):
        return

    st.title("Marketing Portfolio Planner")
    entered = st.text_input("Password", type="password")
    if st.button("Open app", type="primary"):
        if entered == password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()


password_gate()

if "plans" not in st.session_state:
    st.session_state.plans, st.session_state.storage_mode = load_plans()

if "selected_country" not in st.session_state:
    st.session_state.selected_country = st.session_state.plans[0]["country"]


def plan_index(country: str) -> int:
    return next(i for i, p in enumerate(st.session_state.plans) if p["country"] == country)


def update_plan(country: str, field: str, value: Any) -> None:
    idx = plan_index(country)
    st.session_state.plans[idx][field] = value


def reset_country(country: str) -> None:
    baseline = {p["country"]: p for p in load_baseline()}
    idx = plan_index(country)
    st.session_state.plans[idx] = dict(baseline[country])


def portfolio_dataframe() -> pd.DataFrame:
    rows = []
    for plan in st.session_state.plans:
        calc = calculate(plan)
        rows.append({
            "Country": plan["country"],
            "Leads": calc["leads"],
            "Deposit Attempts": calc["deposit_attempts"],
            "FTDs": calc["ftds"],
            "Potential Conversion": plan["potential_conversion"],
            "Approval Ratio": plan["approval_ratio"],
            "FTD Conversion": calc["ftd_conversion"],
            "Marketing Spend": calc["marketing_spend"],
            "CPA": calc["cpa"],
            "PV / FTD": plan["pv_per_ftd"],
            "Net Deposits": calc["net_deposits"],
            "ROI": calc["roi"],
            "PSP Cost": calc["psp_cost"],
            "Net Profit": calc["net_profit"],
            "Profit Margin": calc["profit_margin"],
        })
    return pd.DataFrame(rows).sort_values(
        ["Leads", "Country"], ascending=[False, True]
    ).reset_index(drop=True)


st.markdown(
    """
    <style>
      .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
      div[data-testid="stMetric"] {
        border: 1px solid rgba(128,128,128,.25);
        border-radius: 12px;
        padding: 12px 14px;
        background: rgba(128,128,128,.04);
      }
      .small-note {color: #777; font-size: .85rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("Portfolio Controls")
    countries = sorted(p["country"] for p in st.session_state.plans)
    selected = st.selectbox(
        "Country",
        countries,
        index=countries.index(st.session_state.selected_country),
    )
    st.session_state.selected_country = selected

    storage_mode = st.session_state.get("storage_mode", "Session only")
    st.caption(f"Storage: **{storage_mode}**")

    if st.button("Save current country", type="primary", use_container_width=True):
        plan = st.session_state.plans[plan_index(selected)]
        ok, msg = save_plan(plan)
        (st.success if ok else st.error)(msg)

    if st.button("Save all countries", use_container_width=True):
        count, errors = save_all()
        if errors:
            st.error("\n".join(errors[:5]))
        else:
            st.success(f"Saved {count} countries.")

    if st.button("Reset selected country", use_container_width=True):
        reset_country(selected)
        st.rerun()

    st.divider()
    st.caption(
        "For permanent online saving, configure Supabase secrets. "
        "Without Supabase, local file saving only works reliably on your own computer."
    )

tab_dashboard, tab_calculator, tab_sensitivity, tab_data, tab_formulas = st.tabs(
    ["Portfolio Dashboard", "Country Calculator", "Sensitivity", "Data & Export", "Formulas"]
)

with tab_dashboard:
    st.title("Marketing Portfolio Dashboard")
    portfolio = portfolio_dataframe()

    total_spend = portfolio["Marketing Spend"].sum()
    total_deposits = portfolio["Net Deposits"].sum()
    total_profit = portfolio["Net Profit"].sum()
    total_roi = safe_div(total_deposits, total_spend)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Countries", len(portfolio))
    c2.metric("Total Leads", integer(portfolio["Leads"].sum()))
    c3.metric("Total FTDs", integer(portfolio["FTDs"].sum()))
    c4.metric("Marketing Spend", currency(total_spend))
    c5.metric("Portfolio ROI", multiple(total_roi))
    c6.metric("Net Profit", currency(total_profit))

    st.caption("Sorted automatically by calculated leads, highest first.")

    styled = portfolio.copy()
    styled["Potential Conversion"] = styled["Potential Conversion"].map(pct)
    styled["Approval Ratio"] = styled["Approval Ratio"].map(pct)
    styled["FTD Conversion"] = styled["FTD Conversion"].map(pct)
    styled["Profit Margin"] = styled["Profit Margin"].map(pct)
    styled["ROI"] = styled["ROI"].map(multiple)

    for col in ["Marketing Spend", "CPA", "PV / FTD", "Net Deposits", "PSP Cost", "Net Profit"]:
        styled[col] = styled[col].map(currency)
    for col in ["Leads", "Deposit Attempts", "FTDs"]:
        styled[col] = styled[col].map(integer)

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=620,
        column_config={
            "Country": st.column_config.TextColumn("Country", pinned=True),
        },
    )

    chart_df = portfolio.head(15).set_index("Country")[["Leads", "FTDs"]]
    st.subheader("Top 15 Countries by Leads")
    st.bar_chart(chart_df)

with tab_calculator:
    idx = plan_index(selected)
    plan = st.session_state.plans[idx]
    calc = calculate(plan)

    st.title(f"{selected} Calculator")

    left, right = st.columns([0.34, 0.66], gap="large")

    with left:
        st.subheader("Planning Inputs")

        driver = st.selectbox(
            "Primary driver",
            DRIVERS,
            index=DRIVERS.index(plan["driver"]),
            key=f"driver_{selected}",
        )
        update_plan(selected, "driver", driver)

        if driver == "Marketing Budget":
            driver_value = st.number_input(
                "Marketing budget ($ / month)",
                min_value=0.0,
                value=float(plan["driver_value"]),
                step=1000.0,
                key=f"driver_value_{selected}",
            )
        elif driver == "Target FTDs":
            driver_value = st.number_input(
                "Target FTDs",
                min_value=0.0,
                value=float(plan["driver_value"]),
                step=10.0,
                key=f"driver_value_{selected}",
            )
        else:
            driver_value = st.number_input(
                "Leads purchased",
                min_value=0.0,
                value=float(plan["driver_value"]),
                step=100.0,
                key=f"driver_value_{selected}",
            )
        update_plan(selected, "driver_value", driver_value)

        cpl = st.number_input(
            "CPL ($ / lead)",
            min_value=0.0,
            value=float(plan["cpl"]),
            step=1.0,
            key=f"cpl_{selected}",
        )
        update_plan(selected, "cpl", cpl)

        potential = st.slider(
            "Potential conversion / deposit attempt rate",
            0.0, 1.0, float(plan["potential_conversion"]), 0.001,
            key=f"potential_{selected}",
            help="Percentage of leads who attempt a deposit.",
        )
        update_plan(selected, "potential_conversion", potential)

        approval = st.slider(
            "Approval ratio",
            0.0, 1.0, float(plan["approval_ratio"]), 0.01,
            key=f"approval_{selected}",
            help="Percentage of deposit attempts that are approved.",
        )
        update_plan(selected, "approval_ratio", approval)

        pv = st.number_input(
            "PV / net deposit per FTD ($)",
            min_value=0.0,
            value=float(plan["pv_per_ftd"]),
            step=100.0,
            key=f"pv_{selected}",
        )
        update_plan(selected, "pv_per_ftd", pv)

        psp = st.slider(
            "PSP fee",
            0.0, 0.25, float(plan["psp_fee"]), 0.005,
            key=f"psp_{selected}",
        )
        update_plan(selected, "psp_fee", psp)

        variable = st.number_input(
            "Other variable cost per FTD ($)",
            min_value=0.0,
            value=float(plan["variable_cost_per_ftd"]),
            step=10.0,
            key=f"variable_{selected}",
        )
        update_plan(selected, "variable_cost_per_ftd", variable)

        fixed = st.number_input(
            "Fixed monthly cost ($)",
            min_value=0.0,
            value=float(plan["fixed_monthly_cost"]),
            step=1000.0,
            key=f"fixed_{selected}",
        )
        update_plan(selected, "fixed_monthly_cost", fixed)

        # Recalculate after controls update.
        plan = st.session_state.plans[idx]
        calc = calculate(plan)

    with right:
        st.subheader("Live Performance")

        rows = [
            ("FTD Conversion", pct(calc["ftd_conversion"]), "Potential × approval"),
            ("Leads", integer(calc["leads"]), "Purchased traffic"),
            ("Deposit Attempts", integer(calc["deposit_attempts"]), pct(plan["potential_conversion"]) + " of leads"),
            ("FTDs", integer(calc["ftds"]), pct(plan["approval_ratio"]) + " approved"),
            ("Marketing Spend", currency(calc["marketing_spend"]), "Monthly"),
            ("CPA", currency(calc["cpa"]), "Cost per FTD"),
            ("Net Deposits", currency(calc["net_deposits"]), "FTDs × PV"),
            ("ROI", multiple(calc["roi"]), "Deposits ÷ spend"),
            ("PSP Cost", currency(calc["psp_cost"]), "Processing"),
            ("Net Profit", currency(calc["net_profit"]), "After costs"),
            ("Profit / FTD", currency(calc["profit_per_ftd"]), "After costs"),
            ("Profit Margin", pct(calc["profit_margin"]), "Profit ÷ deposits"),
        ]

        for row_start in range(0, len(rows), 4):
            cols = st.columns(4)
            for col, item in zip(cols, rows[row_start:row_start + 4]):
                col.metric(item[0], item[1], help=item[2])

        st.subheader("Decision Support")
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Break-even CPA", currency(calc["break_even_cpa"]))
        d2.metric("Break-even CPL", currency(calc["break_even_cpl"]))
        d3.metric("Max Profitable Spend", currency(calc["max_profitable_spend"]))
        d4.metric("Budget Headroom", currency(calc["budget_headroom"]))

        funnel = pd.DataFrame(
            {
                "Stage": ["Leads", "Deposit Attempts", "FTDs"],
                "Volume": [calc["leads"], calc["deposit_attempts"], calc["ftds"]],
            }
        ).set_index("Stage")
        st.subheader("Funnel")
        st.bar_chart(funnel)

        with st.expander("Original report reference"):
            st.write({
                "Report leads": integer(plan["report_leads"]),
                "Report FTDs": integer(plan["report_ftds"]),
                "Report conversion": pct(plan["report_conversion_rate"]),
                "Report marketing cost": currency(plan["report_marketing_cost"]),
                "Report CPA": currency(plan["report_cpa"]),
                "Report ROI": multiple(plan["report_roi"]),
                "Report NDP": currency(plan["report_ndp"]),
            })

with tab_sensitivity:
    idx = plan_index(selected)
    plan = st.session_state.plans[idx]

    st.title(f"{selected} Approval-Ratio Sensitivity")
    levels = [x / 100 for x in range(5, 101, 5)]
    rows = []

    for ar in levels:
        scenario = dict(plan)
        scenario["approval_ratio"] = ar
        calc = calculate(scenario)
        rows.append({
            "Approval Ratio": ar,
            "Potential Conversion": scenario["potential_conversion"],
            "FTD Conversion": calc["ftd_conversion"],
            "Leads": calc["leads"],
            "Deposit Attempts": calc["deposit_attempts"],
            "FTDs": calc["ftds"],
            "Marketing Spend": calc["marketing_spend"],
            "CPA": calc["cpa"],
            "Net Deposits": calc["net_deposits"],
            "ROI": calc["roi"],
            "PSP Cost": calc["psp_cost"],
            "Net Profit": calc["net_profit"],
        })

    sensitivity = pd.DataFrame(rows)

    view = sensitivity.copy()
    for col in ["Approval Ratio", "Potential Conversion", "FTD Conversion"]:
        view[col] = view[col].map(pct)
    for col in ["Leads", "Deposit Attempts", "FTDs"]:
        view[col] = view[col].map(integer)
    for col in ["Marketing Spend", "CPA", "Net Deposits", "PSP Cost", "Net Profit"]:
        view[col] = view[col].map(currency)
    view["ROI"] = view["ROI"].map(multiple)

    st.dataframe(view, use_container_width=True, hide_index=True, height=600)

    st.subheader("FTDs by Approval Ratio")
    st.line_chart(sensitivity.set_index("Approval Ratio")[["FTDs"]])

    st.subheader("Net Profit by Approval Ratio")
    st.line_chart(sensitivity.set_index("Approval Ratio")[["Net Profit"]])

with tab_data:
    st.title("Data, Backup & Export")

    portfolio = portfolio_dataframe()
    csv = portfolio.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download portfolio dashboard as CSV",
        data=csv,
        file_name="marketing_portfolio_dashboard.csv",
        mime="text/csv",
        type="primary",
    )

    backup = json.dumps(st.session_state.plans, indent=2).encode("utf-8")
    st.download_button(
        "Download all country assumptions as JSON",
        data=backup,
        file_name="marketing_country_plans_backup.json",
        mime="application/json",
    )

    uploaded = st.file_uploader("Restore assumptions from JSON backup", type=["json"])
    if uploaded is not None:
        try:
            restored = json.load(uploaded)
            countries = {p["country"] for p in load_baseline()}
            restored_countries = {p["country"] for p in restored}
            if countries != restored_countries:
                st.error("Backup country list does not match the app.")
            elif st.button("Apply restored backup"):
                st.session_state.plans = restored
                st.success("Backup restored. Save all countries to persist it.")
                st.rerun()
        except Exception as exc:
            st.error(f"Could not read backup: {exc}")

    st.subheader("Current storage status")
    if get_supabase() is not None:
        st.success("Supabase is configured. Country changes can be saved permanently online.")
    else:
        st.warning(
            "Supabase is not configured. Streamlit Cloud may erase local files whenever the app restarts. "
            "Use the included Supabase setup guide for permanent shared data."
        )

with tab_formulas:
    st.title("Formula Reference")
    st.markdown(
        """
- **Deposit attempts** = Leads × Potential conversion %
- **FTDs** = Deposit attempts × Approval ratio
- **FTD conversion rate** = Potential conversion % × Approval ratio
- **Marketing spend** = Leads × CPL
- **CPA** = Marketing spend ÷ FTDs
- **Net deposits** = FTDs × PV per FTD
- **ROI** = Net deposits ÷ Marketing spend
- **PSP cost** = Net deposits × PSP fee
- **Net marketing profit** = Net deposits − Marketing spend − PSP cost − Variable costs − Fixed costs
- **Break-even CPA** = PV per FTD × (1 − PSP fee) − Variable cost per FTD
- **Break-even CPL** = Break-even CPA × FTD conversion rate
        """
    )
