
import math
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="India Marketing Performance Calculator",
    page_icon="📊",
    layout="wide",
)

# -----------------------------
# Helpers
# -----------------------------
def safe_div(a: float, b: float) -> float:
    return a / b if b not in (0, 0.0) else 0.0

def money(x: float) -> str:
    return f"${x:,.2f}"

def whole(x: float) -> str:
    return f"{x:,.0f}"

def pct(x: float) -> str:
    return f"{x*100:,.2f}%"

def multiple(x: float) -> str:
    return f"{x:,.2f}x"

# -----------------------------
# Baseline from original report
# -----------------------------
BASELINE = {
    "country": "India",
    "leads": 16356,
    "ftds": 1172,
    "conversion_rate": 0.07165566153093667,
    "marketing_cost": 428158.22881640797,
    "cpl": 26.177441233578378,
    "cpa": 365.3227208331126,
    "report_roi": 2.7881567158945892,
    "ndp": 1193772.24114,
}

st.title("India Marketing Budget & Performance Calculator")
st.caption(
    "Change any planning assumption and see the effect on leads, deposit attempts, "
    "FTDs, CPA, ROI, PSP cost, and net marketing profit."
)

with st.sidebar:
    st.header("Planning Controls")

    mode = st.selectbox(
        "Primary driver",
        [
            "Marketing Budget",
            "Target FTDs",
            "Leads Purchased",
        ],
    )

    if mode == "Marketing Budget":
        driver_value = st.number_input(
            "Marketing budget ($ / month)",
            min_value=0.0,
            value=438158.23,
            step=10000.0,
        )
    elif mode == "Target FTDs":
        driver_value = st.number_input(
            "Target FTDs",
            min_value=0,
            value=1200,
            step=50,
        )
    else:
        driver_value = st.number_input(
            "Leads purchased",
            min_value=0,
            value=16738,
            step=500,
        )

    st.divider()
    st.subheader("Funnel Assumptions")

    cpl = st.number_input(
        "CPL ($ / lead)",
        min_value=0.01,
        value=float(BASELINE["cpl"]),
        step=1.0,
    )

    potential_conversion = st.slider(
        "Potential conversion / deposit attempt rate",
        min_value=0.0,
        max_value=1.0,
        value=0.1433,
        step=0.001,
        format="%.3f",
        help="Percentage of leads who attempt a deposit.",
    )

    approval_ratio = st.slider(
        "Approval ratio",
        min_value=0.0,
        max_value=1.0,
        value=0.50,
        step=0.01,
        format="%.2f",
        help="Percentage of deposit attempts that are approved.",
    )

    st.divider()
    st.subheader("Value & Cost Assumptions")

    pv_per_ftd = st.number_input(
        "PV / net deposit per FTD ($)",
        min_value=0.0,
        value=1600.0,
        step=100.0,
    )

    psp_fee = st.slider(
        "PSP fee",
        min_value=0.0,
        max_value=0.25,
        value=0.05,
        step=0.005,
        format="%.3f",
    )

    other_variable_cost = st.number_input(
        "Other variable cost per FTD ($)",
        min_value=0.0,
        value=0.0,
        step=10.0,
    )

    fixed_monthly_cost = st.number_input(
        "Fixed monthly cost ($)",
        min_value=0.0,
        value=0.0,
        step=1000.0,
    )

# -----------------------------
# Core formulas
# -----------------------------
ftd_conversion_rate = potential_conversion * approval_ratio

if mode == "Marketing Budget":
    marketing_spend = float(driver_value)
    leads = safe_div(marketing_spend, cpl)
    deposit_attempts = leads * potential_conversion
    ftds = deposit_attempts * approval_ratio

elif mode == "Target FTDs":
    ftds = float(driver_value)
    deposit_attempts = safe_div(ftds, approval_ratio)
    leads = safe_div(deposit_attempts, potential_conversion)
    marketing_spend = leads * cpl

else:  # Leads Purchased
    leads = float(driver_value)
    marketing_spend = leads * cpl
    deposit_attempts = leads * potential_conversion
    ftds = deposit_attempts * approval_ratio

cpa = safe_div(marketing_spend, ftds)
net_deposits = ftds * pv_per_ftd
roi = safe_div(net_deposits, marketing_spend)
psp_cost = net_deposits * psp_fee
other_variable_total = ftds * other_variable_cost
net_marketing_profit = (
    net_deposits
    - marketing_spend
    - psp_cost
    - other_variable_total
    - fixed_monthly_cost
)
profit_per_ftd = safe_div(net_marketing_profit, ftds)
profit_margin = safe_div(net_marketing_profit, net_deposits)

break_even_cpa = pv_per_ftd * (1 - psp_fee) - other_variable_cost
break_even_cpl = break_even_cpa * ftd_conversion_rate
max_profitable_spend = (
    net_deposits
    - psp_cost
    - other_variable_total
    - fixed_monthly_cost
)
budget_headroom = max_profitable_spend - marketing_spend

# -----------------------------
# KPI dashboard
# -----------------------------
st.subheader("Live Performance")

k1, k2, k3, k4 = st.columns(4)
k1.metric("FTD conversion", pct(ftd_conversion_rate))
k2.metric("Leads purchased", whole(leads))
k3.metric("Deposit attempts", whole(deposit_attempts))
k4.metric("FTDs acquired", whole(ftds))

k5, k6, k7, k8 = st.columns(4)
k5.metric("Marketing spend", money(marketing_spend))
k6.metric("CPA", money(cpa))
k7.metric("Net deposits", money(net_deposits))
k8.metric("ROI", multiple(roi))

k9, k10, k11, k12 = st.columns(4)
k9.metric("PSP cost", money(psp_cost))
k10.metric("Net marketing profit", money(net_marketing_profit))
k11.metric("Profit / FTD", money(profit_per_ftd))
k12.metric("Profit margin", pct(profit_margin))

st.divider()

# -----------------------------
# Decision support
# -----------------------------
st.subheader("Decision Support")
d1, d2, d3, d4 = st.columns(4)
d1.metric("Break-even CPA", money(break_even_cpa))
d2.metric("Break-even CPL", money(break_even_cpl))
d3.metric("Max profitable spend", money(max_profitable_spend))
d4.metric("Budget headroom", money(budget_headroom))

if net_marketing_profit >= 0:
    st.success(
        f"At the current assumptions, the plan generates "
        f"{money(net_marketing_profit)} net marketing profit."
    )
else:
    st.error(
        f"At the current assumptions, the plan loses "
        f"{money(abs(net_marketing_profit))}."
    )

# -----------------------------
# Funnel view
# -----------------------------
st.subheader("Funnel")
funnel = pd.DataFrame(
    {
        "Stage": ["Leads", "Deposit Attempts", "Approved FTDs"],
        "Volume": [leads, deposit_attempts, ftds],
    }
)
st.bar_chart(funnel.set_index("Stage"))

# -----------------------------
# Approval sensitivity
# -----------------------------
st.subheader("Approval Ratio Sensitivity")
approval_levels = [x / 100 for x in range(5, 101, 5)]
rows = []

for ar in approval_levels:
    conv = potential_conversion * ar

    if mode == "Marketing Budget":
        spend_s = marketing_spend
        leads_s = safe_div(spend_s, cpl)
        attempts_s = leads_s * potential_conversion
        ftds_s = attempts_s * ar

    elif mode == "Target FTDs":
        ftds_s = ftds
        attempts_s = safe_div(ftds_s, ar)
        leads_s = safe_div(attempts_s, potential_conversion)
        spend_s = leads_s * cpl

    else:
        leads_s = leads
        spend_s = leads_s * cpl
        attempts_s = leads_s * potential_conversion
        ftds_s = attempts_s * ar

    cpa_s = safe_div(spend_s, ftds_s)
    ndp_s = ftds_s * pv_per_ftd
    roi_s = safe_div(ndp_s, spend_s)
    psp_s = ndp_s * psp_fee
    other_s = ftds_s * other_variable_cost
    profit_s = ndp_s - spend_s - psp_s - other_s - fixed_monthly_cost

    rows.append(
        {
            "Approval Ratio": ar,
            "Potential Conversion": potential_conversion,
            "FTD Conversion": conv,
            "Marketing Spend": spend_s,
            "Leads": leads_s,
            "Deposit Attempts": attempts_s,
            "FTDs": ftds_s,
            "CPA": cpa_s,
            "PV / FTD": pv_per_ftd,
            "Net Deposits": ndp_s,
            "ROI": roi_s,
            "PSP Cost": psp_s,
            "Net Marketing Profit": profit_s,
        }
    )

sensitivity = pd.DataFrame(rows)

display_df = sensitivity.copy()
for col in ["Approval Ratio", "Potential Conversion", "FTD Conversion"]:
    display_df[col] = display_df[col].map(lambda x: f"{x*100:.2f}%")
for col in [
    "Marketing Spend",
    "CPA",
    "PV / FTD",
    "Net Deposits",
    "PSP Cost",
    "Net Marketing Profit",
]:
    display_df[col] = display_df[col].map(lambda x: f"${x:,.2f}")
for col in ["Leads", "Deposit Attempts", "FTDs"]:
    display_df[col] = display_df[col].map(lambda x: f"{x:,.0f}")
display_df["ROI"] = display_df["ROI"].map(lambda x: f"{x:.2f}x")

st.dataframe(display_df, use_container_width=True, hide_index=True)

chart_data = sensitivity.set_index("Approval Ratio")[["FTDs", "Net Marketing Profit"]]
st.line_chart(chart_data)

# -----------------------------
# Current row
# -----------------------------
st.subheader("Current Calculation Row")
current = pd.DataFrame(
    [
        {
            "Approval Ratio": pct(approval_ratio),
            "Potential Conversion": pct(potential_conversion),
            "FTD Conversion": pct(ftd_conversion_rate),
            "Leads": whole(leads),
            "Deposit Attempts": whole(deposit_attempts),
            "FTDs": whole(ftds),
            "CPL": money(cpl),
            "Marketing Spend": money(marketing_spend),
            "CPA": money(cpa),
            "PV / FTD": money(pv_per_ftd),
            "Net Deposits": money(net_deposits),
            "ROI": multiple(roi),
            "PSP Cost": money(psp_cost),
            "Net Marketing Profit": money(net_marketing_profit),
        }
    ]
)
st.dataframe(current, use_container_width=True, hide_index=True)

with st.expander("Formula definitions"):
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
- **Net marketing profit** = Net deposits − Marketing spend − PSP cost − Other variable costs − Fixed costs
        """
    )

st.caption(
    "India baseline source: Amit marketing June 2026 report. "
    "CPL and conversion baseline are preloaded, while all planning inputs are editable."
)
