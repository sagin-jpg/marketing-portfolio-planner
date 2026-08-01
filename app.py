
from __future__ import annotations

import io
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

try:
    from supabase import create_client
except Exception:
    create_client = None

st.set_page_config(
    page_title="FTD Target Control Center",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).parent
BASELINE_PATH = BASE_DIR / "baseline_countries.json"
LOCAL_TARGETS = BASE_DIR / "saved_target_plans.local.json"
LOCAL_ACTUALS = BASE_DIR / "saved_actuals.local.json"

TARGET_TABLE = "ftd_target_plans"
ACTUAL_TABLE = "ftd_actual_snapshots"

NAV_ITEMS = [
    "🏠 Executive Overview",
    "🎯 Target Planner",
    "📊 Actual Data",
    "⚖️ Gap Analysis",
    "🌍 Country Drilldown",
    "🧪 Plan Comparison",
    "📤 Data Hub",
    "⚙️ Settings",
]

THEME = {
    "blue": "#2563EB",
    "green": "#16A34A",
    "red": "#DC2626",
    "amber": "#D97706",
    "purple": "#7C3AED",
    "slate": "#475569",
}


def safe_div(a: float, b: float) -> float:
    return a / b if b not in (0, 0.0) and math.isfinite(b) else 0.0


def currency(x: float) -> str:
    return f"${x:,.0f}"


def number(x: float) -> str:
    return f"{x:,.0f}"


def pct(x: float) -> str:
    return f"{x*100:,.1f}%"


def multiple(x: float) -> str:
    return f"{x:,.1f}x"


def colored_kpi(label: str, value: str, positive: bool) -> None:
    css_class = "kpi-positive" if positive else "kpi-negative"
    st.markdown(
        f"""
        <div class="kpi-box">
          <div class="kpi-label">{label}</div>
          <div class="{css_class}">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data
def baseline_rows() -> list[dict[str, Any]]:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def get_supabase():
    if create_client is None:
        return None
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception:
        return None


def plan_defaults(plan_name: str, month: str) -> list[dict[str, Any]]:
    rows = []
    for base in baseline_rows():
        row = dict(base)
        row.update({
            "plan_name": plan_name,
            "plan_month": month,
            "target_ftds": base["default_target_ftds"],
        })
        rows.append(row)
    return rows


def normalize_plan_row(row: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "target_ftds": 0.0,
        "potential_conversion": 0.0,
        "approval_ratio": 0.5,
        "cpl": 0.0,
        "pv_per_ftd": 1600.0,
        "psp_fee": 0.05,
        "variable_cost_per_ftd": 0.0,
        "fixed_cost": 0.0,
    }
    result = dict(row)
    for k, v in defaults.items():
        result[k] = float(result.get(k, v) or 0)
    return result


def load_target_plans() -> dict[str, list[dict[str, Any]]]:
    supa = get_supabase()
    if supa is not None:
        try:
            rows = supa.table(TARGET_TABLE).select("plan_key,payload").execute().data or []
            if rows:
                return {r["plan_key"]: r["payload"] for r in rows}
        except Exception as exc:
            st.warning(f"Could not read target plans from Supabase: {exc}")

    if LOCAL_TARGETS.exists():
        try:
            return json.loads(LOCAL_TARGETS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_target_plan(plan_key: str, payload: list[dict[str, Any]]) -> tuple[bool, str]:
    supa = get_supabase()
    if supa is not None:
        try:
            supa.table(TARGET_TABLE).upsert({
                "plan_key": plan_key,
                "payload": payload,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, on_conflict="plan_key").execute()
            return True, "Plan saved to Supabase"
        except Exception as exc:
            return False, f"Supabase save failed: {exc}"

    try:
        plans = st.session_state.saved_plans
        plans[plan_key] = payload
        LOCAL_TARGETS.write_text(json.dumps(plans, indent=2), encoding="utf-8")
        return True, "Plan saved locally"
    except Exception:
        return False, "No permanent storage configured"


def delete_target_plan(plan_key: str) -> tuple[bool, str]:
    supa = get_supabase()
    if supa is not None:
        try:
            supa.table(TARGET_TABLE).delete().eq("plan_key", plan_key).execute()
            return True, "Deleted"
        except Exception as exc:
            return False, str(exc)

    try:
        st.session_state.saved_plans.pop(plan_key, None)
        LOCAL_TARGETS.write_text(json.dumps(st.session_state.saved_plans, indent=2), encoding="utf-8")
        return True, "Deleted"
    except Exception:
        return False, "Delete failed"


def load_actuals() -> list[dict[str, Any]]:
    supa = get_supabase()
    if supa is not None:
        try:
            rows = supa.table(ACTUAL_TABLE).select("*").execute().data or []
            return rows
        except Exception as exc:
            st.warning(f"Could not read actual data from Supabase: {exc}")

    if LOCAL_ACTUALS.exists():
        try:
            return json.loads(LOCAL_ACTUALS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_actual_rows(rows: list[dict[str, Any]]) -> tuple[bool, str]:
    supa = get_supabase()
    if supa is not None:
        try:
            supa.table(ACTUAL_TABLE).upsert(
                rows,
                on_conflict="snapshot_date,country",
            ).execute()
            return True, f"Saved {len(rows)} actual rows to Supabase"
        except Exception as exc:
            return False, f"Supabase save failed: {exc}"

    try:
        existing = {(r["snapshot_date"], r["country"]): r for r in st.session_state.actual_rows}
        for row in rows:
            existing[(row["snapshot_date"], row["country"])] = row
        st.session_state.actual_rows = list(existing.values())
        LOCAL_ACTUALS.write_text(json.dumps(st.session_state.actual_rows, indent=2), encoding="utf-8")
        return True, f"Saved {len(rows)} actual rows locally"
    except Exception:
        return False, "No permanent storage configured"


def calculate_target(row: dict[str, Any]) -> dict[str, float]:
    r = normalize_plan_row(row)
    target_ftds = max(0.0, r["target_ftds"])
    potential = min(max(r["potential_conversion"], 0.0), 1.0)
    approval = min(max(r["approval_ratio"], 0.0), 1.0)
    # Final lead-to-FTD conversion is driven by both deposit intent and payment approval.
    # CPA therefore moves automatically with CPL, potential conversion, and approval ratio.
    conversion = potential * approval
    attempts = safe_div(target_ftds, approval)
    leads = safe_div(target_ftds, conversion)
    spend = leads * max(0.0, r["cpl"])
    cpa = safe_div(max(0.0, r["cpl"]), conversion)
    ndp = target_ftds * max(0.0, r["pv_per_ftd"])
    roi = safe_div(ndp, spend)
    psp = ndp * min(max(r["psp_fee"], 0.0), 1.0)
    variable = target_ftds * max(0.0, r["variable_cost_per_ftd"])
    profit = ndp - spend - psp - variable - max(0.0, r["fixed_cost"])
    return {
        "target_ftds": target_ftds,
        "target_leads": leads,
        "target_attempts": attempts,
        "target_conversion": conversion,
        "target_spend": spend,
        "target_cpa": cpa,
        "target_ndp": ndp,
        "target_roi": roi,
        "target_gross_profitability": ndp - spend,
        "target_profit": profit,
    }


def parse_uploaded_file(uploaded, snapshot_date: date) -> pd.DataFrame:
    name = uploaded.name.lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        raw = pd.read_excel(uploaded)
    elif name.endswith(".csv"):
        raw = pd.read_csv(uploaded)
    else:
        raise ValueError("Use .xlsx or .csv")

    raw.columns = [str(c).strip().lower() for c in raw.columns]
    aliases = {
        "row labels": "country",
        "country": "country",
        "leads": "leads",
        "ftd #": "ftds",
        "ftds": "ftds",
        "ftd": "ftds",
        "cr %": "conversion_rate",
        "conversion": "conversion_rate",
        "conversion_rate": "conversion_rate",
        "cost": "marketing_cost",
        "marketing cost": "marketing_cost",
        "marketing_cost": "marketing_cost",
        "cpl": "cpl",
        "avg cpa": "cpa",
        "cpa": "cpa",
        "roi": "roi",
        "ndp$": "ndp",
        "ndp": "ndp",
        "net deposits": "ndp",
        "date": "snapshot_date",
        "snapshot_date": "snapshot_date",
    }
    raw = raw.rename(columns={c: aliases.get(c, c) for c in raw.columns})

    if "country" not in raw.columns:
        raise ValueError("The file must contain a Country or Row Labels column.")

    for required in ["leads", "ftds", "marketing_cost", "ndp"]:
        if required not in raw.columns:
            raw[required] = 0.0

    if "conversion_rate" not in raw.columns:
        raw["conversion_rate"] = raw.apply(lambda x: safe_div(float(x["ftds"]), float(x["leads"])), axis=1)
    if "cpl" not in raw.columns:
        raw["cpl"] = raw.apply(lambda x: safe_div(float(x["marketing_cost"]), float(x["leads"])), axis=1)
    if "cpa" not in raw.columns:
        raw["cpa"] = raw.apply(lambda x: safe_div(float(x["marketing_cost"]), float(x["ftds"])), axis=1)
    if "roi" not in raw.columns:
        raw["roi"] = raw.apply(lambda x: safe_div(float(x["ndp"]), float(x["marketing_cost"])), axis=1)

    if "snapshot_date" not in raw.columns:
        raw["snapshot_date"] = snapshot_date.isoformat()
    else:
        raw["snapshot_date"] = pd.to_datetime(raw["snapshot_date"]).dt.date.astype(str)

    raw["country"] = raw["country"].astype(str).str.strip()
    raw = raw[raw["country"].ne("")]
    raw = raw[~raw["country"].str.lower().isin(["grand total", "total"])]

    numeric_cols = ["leads","ftds","conversion_rate","marketing_cost","cpl","cpa","roi","ndp"]
    for c in numeric_cols:
        raw[c] = pd.to_numeric(raw[c], errors="coerce").fillna(0.0)

    return raw[["snapshot_date","country","leads","ftds","conversion_rate","marketing_cost","cpl","cpa","roi","ndp"]]


def current_plan_rows() -> list[dict[str, Any]]:
    return st.session_state.current_plan


def target_df() -> pd.DataFrame:
    rows = []
    for row in current_plan_rows():
        calc = calculate_target(row)
        rows.append({
            "country": row["country"],
            **calc,
            "potential_conversion": row["potential_conversion"],
            "approval_ratio": row["approval_ratio"],
            "cpl": row["cpl"],
            "pv_per_ftd": row["pv_per_ftd"],
            "psp_fee": row["psp_fee"],
        })
    return pd.DataFrame(rows)


def actual_df() -> pd.DataFrame:
    if not st.session_state.actual_rows:
        return pd.DataFrame(columns=["snapshot_date","country","leads","ftds","conversion_rate","marketing_cost","cpl","cpa","roi","ndp"])
    df = pd.DataFrame(st.session_state.actual_rows)
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    return df


def latest_actual_by_country() -> pd.DataFrame:
    df = actual_df()
    if df.empty:
        return df
    idx = df.groupby("country")["snapshot_date"].idxmax()
    return df.loc[idx].copy()


def gap_df() -> pd.DataFrame:
    t = target_df()
    a = latest_actual_by_country()
    merged = t.merge(a, on="country", how="left", suffixes=("_target", "_actual"))
    for col in ["leads","ftds","conversion_rate","marketing_cost","cpl","cpa","roi","ndp"]:
        if col not in merged:
            merged[col] = 0.0
        merged[col] = merged[col].fillna(0.0)

    merged["ftd_gap"] = merged["ftds"] - merged["target_ftds"]
    merged["ftd_attainment"] = merged.apply(lambda r: safe_div(r["ftds"], r["target_ftds"]), axis=1)
    merged["lead_gap"] = merged["leads"] - merged["target_leads"]
    merged["spend_gap"] = merged["marketing_cost"] - merged["target_spend"]
    merged["cpa_gap"] = merged["cpa"] - merged["target_cpa"]
    merged["actual_gross_profitability"] = merged["ndp"] - merged["marketing_cost"]
    merged["target_gross_profitability"] = (
        merged["target_ndp"] - merged["target_spend"]
    )
    merged["gross_profitability_gap"] = (
        merged["actual_gross_profitability"]
        - merged["target_gross_profitability"]
    )
    merged["ndp_gap"] = merged["ndp"] - merged["target_ndp"]
    return merged


def password_gate():
    password = st.secrets.get("APP_PASSWORD", "")
    if not password:
        return
    if st.session_state.get("authenticated"):
        return
    st.title("FTD Target Control Center")
    entered = st.text_input("Password", type="password")
    if st.button("Open", type="primary"):
        if entered == password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()


password_gate()

if "saved_plans" not in st.session_state:
    st.session_state.saved_plans = load_target_plans()
if "actual_rows" not in st.session_state:
    st.session_state.actual_rows = load_actuals()
if "current_plan_key" not in st.session_state:
    st.session_state.current_plan_key = "Base Plan | 2026-06"
if "current_plan" not in st.session_state:
    if st.session_state.current_plan_key in st.session_state.saved_plans:
        st.session_state.current_plan = st.session_state.saved_plans[st.session_state.current_plan_key]
    else:
        st.session_state.current_plan = plan_defaults("Base Plan", "2026-06")

st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 2rem;}
div[data-testid="stMetric"] {
  border: 1px solid rgba(100,116,139,.22);
  border-radius: 14px;
  padding: 14px 16px;
  background: linear-gradient(180deg, rgba(255,255,255,.96), rgba(248,250,252,.96));
  box-shadow: 0 8px 24px rgba(15,23,42,.04);
}
div[role="radiogroup"] {display:flex; flex-wrap:wrap; gap:.45rem;}
div[role="radiogroup"] label {
  border:1px solid rgba(100,116,139,.25);
  border-radius:10px;
  padding:.45rem .75rem;
  background:rgba(148,163,184,.06);
}
div[role="radiogroup"] label p {font-weight:650!important; color:#334155!important;}
div[role="radiogroup"] label:has(input:checked) {
  background:rgba(37,99,235,.10);
  border-color:#2563EB;
}
div[role="radiogroup"] label:has(input:checked) p {color:#2563EB!important;}
.kpi-positive {
  color: #16A34A;
  font-size: 2rem;
  font-weight: 750;
  line-height: 1.1;
}
.kpi-negative {
  color: #DC2626;
  font-size: 2rem;
  font-weight: 750;
  line-height: 1.1;
}
.kpi-label {
  color: #475569;
  font-size: .9rem;
  margin-bottom: .25rem;
}
.kpi-box {
  border: 1px solid rgba(100,116,139,.22);
  border-radius: 14px;
  padding: 14px 16px;
  background: linear-gradient(180deg, rgba(255,255,255,.96), rgba(248,250,252,.96));
  box-shadow: 0 8px 24px rgba(15,23,42,.04);
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("🎯 FTD Control Center")

    nav = st.radio("Navigation", NAV_ITEMS, label_visibility="collapsed")

    st.divider()
    st.subheader("Active Plan")

    saved_keys = sorted(st.session_state.saved_plans.keys())
    plan_options = saved_keys + ["➕ New plan"]
    selected_key = st.selectbox(
        "Saved plan",
        plan_options,
        index=plan_options.index(st.session_state.current_plan_key)
        if st.session_state.current_plan_key in plan_options else len(plan_options)-1,
    )

    if selected_key == "➕ New plan":
        new_name = st.text_input("Plan name", value="New Target Plan")
        new_month = st.text_input("Plan month", value=date.today().strftime("%Y-%m"))
        if st.button("Create plan", type="primary", use_container_width=True):
            key = f"{new_name} | {new_month}"
            st.session_state.current_plan_key = key
            st.session_state.current_plan = plan_defaults(new_name, new_month)
            st.rerun()
    elif selected_key != st.session_state.current_plan_key:
        st.session_state.current_plan_key = selected_key
        st.session_state.current_plan = st.session_state.saved_plans[selected_key]
        st.rerun()

    if st.button("Save active plan", type="primary", use_container_width=True):
        key = st.session_state.current_plan_key
        ok, msg = save_target_plan(key, st.session_state.current_plan)
        if ok:
            st.session_state.saved_plans[key] = st.session_state.current_plan
            st.success(msg)
        else:
            st.error(msg)

    if st.button("Duplicate active plan", use_container_width=True):
        base_key = st.session_state.current_plan_key
        copy_key = base_key + " Copy"
        st.session_state.current_plan_key = copy_key
        st.session_state.current_plan = json.loads(json.dumps(st.session_state.current_plan))
        st.rerun()

    if st.button("Delete active plan", use_container_width=True):
        key = st.session_state.current_plan_key
        ok, msg = delete_target_plan(key)
        if ok:
            st.session_state.saved_plans.pop(key, None)
            st.session_state.current_plan_key = "Base Plan | 2026-06"
            st.session_state.current_plan = plan_defaults("Base Plan", "2026-06")
            st.rerun()
        else:
            st.error(msg)

    st.divider()
    storage = "Supabase" if get_supabase() else "Local/session"
    st.caption(f"Storage: **{storage}**")

st.title("FTD Target Control Center")
st.caption("Power BI–style target planning, daily actual uploads, and real-time gap control.")

if nav == "🏠 Executive Overview":
    target = target_df()
    actual = latest_actual_by_country()
    gap = gap_df()

    target_ftds = target["target_ftds"].sum()
    actual_ftds = actual["ftds"].sum() if not actual.empty else 0
    attainment = safe_div(actual_ftds, target_ftds)
    target_spend = target["target_spend"].sum()
    actual_spend = actual["marketing_cost"].sum() if not actual.empty else 0
    target_ndp = target["target_ndp"].sum()
    actual_ndp = actual["ndp"].sum() if not actual.empty else 0

    st.subheader("Portfolio Scorecard")
    target_roi_total = safe_div(target_ndp, target_spend)
    actual_roi_total = safe_div(actual_ndp, actual_spend)
    actual_gross_profitability = actual_ndp - actual_spend

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Target FTDs", number(target_ftds))
    c2.metric("Actual FTDs", number(actual_ftds), delta=number(actual_ftds-target_ftds))
    c3.metric("Attainment", pct(attainment))
    c4.metric("Target Spend", currency(target_spend))
    c5.metric("Actual Spend", currency(actual_spend), delta=currency(actual_spend-target_spend))
    c6.metric("NDP Gap", currency(actual_ndp-target_ndp))

    r1, r2, r3 = st.columns(3)
    with r1:
        colored_kpi("Target ROI", multiple(target_roi_total), target_roi_total >= 1.0)
    with r2:
        colored_kpi("Actual ROI", multiple(actual_roi_total), actual_roi_total >= 1.0)
    with r3:
        colored_kpi(
            "Gross Marketing Profitability",
            currency(actual_gross_profitability),
            actual_gross_profitability >= 0,
        )

    col1, col2 = st.columns([0.42,0.58])
    with col1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=attainment*100,
            delta={"reference":100},
            title={"text":"FTD Attainment %"},
            gauge={
                "axis":{"range":[0,130]},
                "bar":{"color":THEME["blue"]},
                "steps":[
                    {"range":[0,80],"color":"#FEE2E2"},
                    {"range":[80,100],"color":"#FEF3C7"},
                    {"range":[100,130],"color":"#DCFCE7"},
                ],
                "threshold":{"line":{"color":THEME["green"],"width":4},"value":100},
            }
        ))
        fig.update_layout(height=340, margin=dict(l=20,r=20,t=50,b=20))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        top_gap = gap.sort_values("ftd_gap").head(12)
        fig = px.bar(
            top_gap,
            x="ftd_gap",
            y="country",
            orientation="h",
            color="ftd_gap",
            color_continuous_scale=["#DC2626","#F8FAFC","#16A34A"],
            title="Largest FTD Gaps",
        )
        fig.update_layout(height=340, coloraxis_showscale=False, yaxis_title="", xaxis_title="Actual - Target FTDs")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Country Performance Matrix")
    matrix = gap[[
        "country","target_ftds","ftds","ftd_gap","ftd_attainment",
        "target_spend","marketing_cost","spend_gap",
        "target_cpa","cpa","cpa_gap","target_ndp","ndp","ndp_gap",
        "target_gross_profitability","actual_gross_profitability",
        "gross_profitability_gap"
    ]].sort_values("target_ftds", ascending=False)

    # Add a highlighted portfolio total row above the first country row.
    total_target_ftds = matrix["target_ftds"].sum()
    total_actual_ftds = matrix["ftds"].sum()
    total_target_spend = matrix["target_spend"].sum()
    total_actual_spend = matrix["marketing_cost"].sum()
    total_target_ndp = matrix["target_ndp"].sum()
    total_actual_ndp = matrix["ndp"].sum()

    total_row = pd.DataFrame([{
        "country": "TOTAL PORTFOLIO",
        "target_ftds": total_target_ftds,
        "ftds": total_actual_ftds,
        "ftd_gap": total_actual_ftds - total_target_ftds,
        "ftd_attainment": safe_div(total_actual_ftds, total_target_ftds),
        "target_spend": total_target_spend,
        "marketing_cost": total_actual_spend,
        "spend_gap": total_actual_spend - total_target_spend,
        "target_cpa": safe_div(total_target_spend, total_target_ftds),
        "cpa": safe_div(total_actual_spend, total_actual_ftds),
        "cpa_gap": (
            safe_div(total_actual_spend, total_actual_ftds)
            - safe_div(total_target_spend, total_target_ftds)
        ),
        "target_ndp": total_target_ndp,
        "ndp": total_actual_ndp,
        "ndp_gap": total_actual_ndp - total_target_ndp,
        "target_gross_profitability": (
            matrix["target_gross_profitability"].sum()
        ),
        "actual_gross_profitability": (
            matrix["actual_gross_profitability"].sum()
        ),
        "gross_profitability_gap": (
            matrix["gross_profitability_gap"].sum()
        ),
    }])

    matrix_with_total = pd.concat([total_row, matrix], ignore_index=True)

    display = matrix_with_total.copy()
    for c in ["target_ftds","ftds","ftd_gap"]:
        display[c] = display[c].map(number)
    display["ftd_attainment"] = display["ftd_attainment"].map(pct)
    for c in [
        "target_spend","marketing_cost","spend_gap","target_cpa","cpa","cpa_gap",
        "target_ndp","ndp","ndp_gap","target_gross_profitability",
        "actual_gross_profitability","gross_profitability_gap"
    ]:
        display[c] = display[c].map(currency)

    display.columns = [
        "Country","Target FTDs","Actual FTDs","FTD Gap","Attainment",
        "Target Spend","Actual Spend","Spend Gap","Target CPA","Actual CPA","CPA Gap",
        "Target NDP","Actual NDP","NDP Gap","Target Gross Profitability",
        "Actual Gross Profitability","Gross Profitability Gap"
    ]

    def highlight_total_row(row):
        if row["Country"] == "TOTAL PORTFOLIO":
            return [
                "background-color: #DBEAFE; color: #0F172A; font-weight: 800;"
                for _ in row
            ]
        return ["" for _ in row]

    styled_display = display.style.apply(highlight_total_row, axis=1)

    st.dataframe(
        styled_display,
        use_container_width=True,
        hide_index=True,
        height=620,
        column_config={
            "Country": st.column_config.TextColumn("Country", pinned=True),
        },
    )

elif nav == "🎯 Target Planner":
    st.subheader(f"Target Planner — {st.session_state.current_plan_key}")

    plan_df = pd.DataFrame(st.session_state.current_plan)
    editor_cols = [
        "country","target_ftds","potential_conversion","approval_ratio",
        "cpl","pv_per_ftd","psp_fee","variable_cost_per_ftd","fixed_cost"
    ]

    edited = st.data_editor(
        plan_df[editor_cols],
        use_container_width=True,
        hide_index=True,
        height=620,
        disabled=["country"],
        column_config={
            "country": st.column_config.TextColumn("Country", pinned=True),
            "target_ftds": st.column_config.NumberColumn("Target FTDs", min_value=0, step=10),
            "potential_conversion": st.column_config.NumberColumn("Potential Conversion", min_value=0, max_value=1, format="%.2f"),
            "approval_ratio": st.column_config.NumberColumn("Approval Ratio", min_value=0, max_value=1, format="%.2f"),
            "cpl": st.column_config.NumberColumn("CPL", min_value=0, format="$%.2f"),
            "pv_per_ftd": st.column_config.NumberColumn("PV / FTD", min_value=0, format="$%.2f"),
            "psp_fee": st.column_config.NumberColumn("PSP Fee", min_value=0, max_value=1, format="%.3f"),
            "variable_cost_per_ftd": st.column_config.NumberColumn("Variable Cost / FTD", min_value=0, format="$%.2f"),
            "fixed_cost": st.column_config.NumberColumn("Fixed Cost", min_value=0, format="$%.2f"),
        },
        key="target_editor",
    )

    lookup = {r["country"]: r for r in st.session_state.current_plan}
    for _, r in edited.iterrows():
        country = r["country"]
        for c in editor_cols[1:]:
            lookup[country][c] = float(r[c])
    st.session_state.current_plan = list(lookup.values())

    t = target_df().sort_values("target_ftds", ascending=False)

    st.subheader("CPA Driver Calculator")
    st.caption(
        "CPA updates automatically from the complete funnel: "
        "CPA = CPL ÷ (Potential Conversion × Approval Ratio)."
    )

    selected_calc_country = st.selectbox(
        "Country for CPA simulation",
        sorted(t["country"].tolist()),
        key="cpa_sim_country",
    )
    sim_row = t[t["country"] == selected_calc_country].iloc[0]

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("CPL", currency(sim_row["cpl"]))
    s2.metric("Potential Conversion", pct(sim_row["potential_conversion"]))
    s3.metric("Approval Ratio", pct(sim_row["approval_ratio"]))
    s4.metric("Calculated CPA", currency(sim_row["target_cpa"]))

    st.markdown(
        f"""
        **{selected_calc_country} calculation**

        `{currency(sim_row["cpl"])} ÷ ({pct(sim_row["potential_conversion"])} × {pct(sim_row["approval_ratio"])}) = {currency(sim_row["target_cpa"])}`

        Final lead-to-FTD conversion: **{pct(sim_row["target_conversion"])}**
        """
    )

    st.subheader("Target Economics")
    target_spend_total = t["target_spend"].sum()
    target_ndp_total = t["target_ndp"].sum()
    target_roi_total = safe_div(target_ndp_total, target_spend_total)
    target_gross_profitability_total = (
        target_ndp_total - target_spend_total
    )

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Target FTDs", number(t["target_ftds"].sum()))
    c2.metric("Required Leads", number(t["target_leads"].sum()))
    c3.metric("Marketing Spend", currency(target_spend_total))
    c4.metric("Target NDP", currency(target_ndp_total))
    c5.metric("Target Profit", currency(t["target_profit"].sum()))

    p1, p2 = st.columns(2)
    with p1:
        colored_kpi("Target ROI", multiple(target_roi_total), target_roi_total >= 1.0)
    with p2:
        colored_kpi(
            "Gross Marketing Profitability",
            currency(target_gross_profitability_total),
            target_gross_profitability_total >= 0,
        )

    fig = px.treemap(
        t[t["target_ftds"]>0],
        path=["country"],
        values="target_ftds",
        color="target_roi",
        color_continuous_scale="Blues",
        title="Target FTD Allocation by Country",
    )
    fig.update_layout(height=520)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("CPA Sensitivity Heatmap")
    selected_plan_row = next(
        r for r in st.session_state.current_plan
        if r["country"] == selected_calc_country
    )
    approval_levels = [x / 100 for x in range(10, 101, 5)]
    potential_levels = [x / 100 for x in range(5, 51, 5)]
    heat_rows = []
    for potential_level in potential_levels:
        heat_rows.append([
            safe_div(
                float(selected_plan_row["cpl"]),
                potential_level * approval_level,
            )
            for approval_level in approval_levels
        ])

    heatmap = go.Figure(
        data=go.Heatmap(
            z=heat_rows,
            x=[f"{x*100:.0f}%" for x in approval_levels],
            y=[f"{x*100:.0f}%" for x in potential_levels],
            colorscale="RdYlGn_r",
            colorbar={"title": "CPA ($)"},
            hovertemplate=(
                "Approval: %{x}<br>"
                "Potential conversion: %{y}<br>"
                "CPA: $%{z:,.2f}<extra></extra>"
            ),
        )
    )
    heatmap.update_layout(
        height=520,
        xaxis_title="Approval Ratio",
        yaxis_title="Potential Conversion / Deposit Attempt Rate",
    )
    st.plotly_chart(heatmap, use_container_width=True)

elif nav == "📊 Actual Data":
    st.subheader("Daily Actual Data Upload")
    st.info(
        "Upload the same Excel structure as your original report, or a CSV/XLSX with columns: "
        "Country, Leads, FTDs, Marketing Cost, NDP. Date is optional."
    )

    col1, col2 = st.columns([0.35,0.65])
    with col1:
        snapshot_date = st.date_input("Snapshot date", value=date.today())
        uploaded = st.file_uploader("Upload actual data", type=["xlsx","xls","csv"])

        if uploaded:
            try:
                parsed = parse_uploaded_file(uploaded, snapshot_date)
                st.success(f"Recognized {len(parsed)} country rows.")
                st.dataframe(parsed.head(10), use_container_width=True, hide_index=True)

                if st.button("Save uploaded actual data", type="primary"):
                    rows = parsed.to_dict("records")
                    ok, msg = save_actual_rows(rows)
                    if ok:
                        existing = {(r["snapshot_date"],r["country"]):r for r in st.session_state.actual_rows}
                        for r in rows:
                            existing[(r["snapshot_date"],r["country"])] = r
                        st.session_state.actual_rows = list(existing.values())
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            except Exception as exc:
                st.error(str(exc))

    with col2:
        actual = actual_df()
        if actual.empty:
            st.warning("No actual snapshots uploaded yet.")
        else:
            latest_date = actual["snapshot_date"].max().date()
            st.metric("Latest Snapshot", latest_date.strftime("%d %b %Y"))
            trend = actual.groupby("snapshot_date", as_index=False)[["leads","ftds","marketing_cost","ndp"]].sum()
            fig = px.line(trend, x="snapshot_date", y=["ftds","leads"], markers=True, title="Portfolio Actual Trend")
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Uploaded Snapshots")
            summary = actual.groupby("snapshot_date", as_index=False).agg(
                countries=("country","nunique"),
                leads=("leads","sum"),
                ftds=("ftds","sum"),
                marketing_cost=("marketing_cost","sum"),
                ndp=("ndp","sum"),
            ).sort_values("snapshot_date", ascending=False)
            st.dataframe(summary, use_container_width=True, hide_index=True)

elif nav == "⚖️ Gap Analysis":
    st.subheader("Reality vs Target Gap Control")
    gap = gap_df()

    if latest_actual_by_country().empty:
        st.warning("Upload actual data first.")
    else:
        filters = st.columns(3)
        with filters[0]:
            min_attain = st.slider("Minimum attainment filter", 0.0, 1.5, 0.0, 0.05)
        with filters[1]:
            only_negative = st.checkbox("Only countries below target")
        with filters[2]:
            top_n = st.number_input("Top countries", 5, 29, 15)

        filtered = gap[gap["ftd_attainment"] >= min_attain]
        if only_negative:
            filtered = filtered[filtered["ftd_gap"] < 0]
        filtered = filtered.sort_values("ftd_gap").head(int(top_n))

        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Total FTD Gap", number(gap["ftd_gap"].sum()))
        c2.metric("Spend Gap", currency(gap["spend_gap"].sum()))
        c3.metric("NDP Gap", currency(gap["ndp_gap"].sum()))
        c4.metric(
            "Gross Profitability Gap",
            currency(gap["gross_profitability_gap"].sum()),
        )
        c5.metric("Countries Below Target", int((gap["ftd_gap"]<0).sum()))

        fig = px.bar(
            filtered,
            x="country",
            y=["target_ftds","ftds"],
            barmode="group",
            title="Target vs Actual FTDs",
            labels={"value":"FTDs","variable":"Series"},
        )
        st.plotly_chart(fig, use_container_width=True)

        heat = gap[["country","ftd_attainment","cpa_gap","spend_gap","ndp_gap"]].copy()
        heat = heat.sort_values("ftd_attainment")
        fig = px.scatter(
            heat,
            x="ftd_attainment",
            y="cpa_gap",
            size=heat["spend_gap"].abs()+1,
            color="ndp_gap",
            hover_name="country",
            color_continuous_scale=["#DC2626","#F8FAFC","#16A34A"],
            title="Gap Risk Map",
            labels={"ftd_attainment":"FTD Attainment","cpa_gap":"CPA Gap"},
        )
        fig.add_vline(x=1, line_dash="dash", line_color="#16A34A")
        fig.add_hline(y=0, line_dash="dash", line_color="#64748B")
        st.plotly_chart(fig, use_container_width=True)

        export = gap.to_csv(index=False).encode()
        st.download_button("Download complete gap report", export, "ftd_gap_report.csv", "text/csv")

elif nav == "🌍 Country Drilldown":
    st.subheader("Country Drilldown")
    countries = sorted([r["country"] for r in current_plan_rows()])
    selected_country = st.selectbox("Country", countries)

    target = target_df()
    trow = target[target["country"]==selected_country].iloc[0]
    actual_all = actual_df()
    country_actual = actual_all[actual_all["country"]==selected_country].sort_values("snapshot_date")

    if country_actual.empty:
        arow = pd.Series({c:0 for c in ["ftds","leads","marketing_cost","cpa","ndp","roi"]})
    else:
        arow = country_actual.iloc[-1]

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Target FTDs", number(trow["target_ftds"]))
    c2.metric("Actual FTDs", number(arow["ftds"]), delta=number(arow["ftds"]-trow["target_ftds"]))
    c3.metric("Target CPA", currency(trow["target_cpa"]))
    c4.metric("Actual CPA", currency(arow["cpa"]), delta=currency(arow["cpa"]-trow["target_cpa"]))
    c5.metric("Target Spend", currency(trow["target_spend"]))
    c6.metric("Actual Spend", currency(arow["marketing_cost"]), delta=currency(arow["marketing_cost"]-trow["target_spend"]))

    target_country_roi = safe_div(trow["target_ndp"], trow["target_spend"])
    actual_country_roi = safe_div(arow["ndp"], arow["marketing_cost"])
    target_country_gross = trow["target_ndp"] - trow["target_spend"]
    actual_country_gross = arow["ndp"] - arow["marketing_cost"]

    rr1, rr2, rr3, rr4 = st.columns(4)
    with rr1:
        colored_kpi("Target ROI", multiple(target_country_roi), target_country_roi >= 1.0)
    with rr2:
        colored_kpi("Actual ROI", multiple(actual_country_roi), actual_country_roi >= 1.0)
    with rr3:
        colored_kpi(
            "Target Gross Profitability",
            currency(target_country_gross),
            target_country_gross >= 0,
        )
    with rr4:
        colored_kpi(
            "Actual Gross Profitability",
            currency(actual_country_gross),
            actual_country_gross >= 0,
        )

    if not country_actual.empty:
        fig = px.line(
            country_actual,
            x="snapshot_date",
            y=["ftds","leads","marketing_cost","ndp"],
            markers=True,
            title=f"{selected_country} Actual Trend",
        )
        st.plotly_chart(fig, use_container_width=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Target", x=["FTDs","Leads","Spend","NDP"], y=[
        trow["target_ftds"], trow["target_leads"], trow["target_spend"], trow["target_ndp"]
    ]))
    fig.add_trace(go.Bar(name="Actual", x=["FTDs","Leads","Spend","NDP"], y=[
        arow["ftds"], arow["leads"], arow["marketing_cost"], arow["ndp"]
    ]))
    fig.update_layout(barmode="group", title=f"{selected_country} Target vs Actual")
    st.plotly_chart(fig, use_container_width=True)

elif nav == "🧪 Plan Comparison":
    st.subheader("Saved Plan Comparison")
    keys = sorted(st.session_state.saved_plans.keys())
    if len(keys) < 2:
        st.warning("Save at least two plans to compare them.")
    else:
        selected = st.multiselect("Choose plans", keys, default=keys[:2], max_selections=4)
        rows = []
        for key in selected:
            for row in st.session_state.saved_plans[key]:
                calc = calculate_target(row)
                rows.append({"plan":key,"country":row["country"],**calc})
        comp = pd.DataFrame(rows)
        if not comp.empty:
            summary = comp.groupby("plan", as_index=False).agg(
                target_ftds=("target_ftds","sum"),
                target_leads=("target_leads","sum"),
                target_spend=("target_spend","sum"),
                target_ndp=("target_ndp","sum"),
                target_profit=("target_profit","sum"),
            )
            summary["target_roi"] = summary.apply(
                lambda r: safe_div(r["target_ndp"], r["target_spend"]),
                axis=1,
            )
            summary["gross_marketing_profitability"] = (
                summary["target_ndp"] - summary["target_spend"]
            )
            st.dataframe(summary, use_container_width=True, hide_index=True)
            fig = px.bar(summary, x="plan", y=["target_ftds","target_spend","target_profit"], barmode="group")
            st.plotly_chart(fig, use_container_width=True)

elif nav == "📤 Data Hub":
    st.subheader("Data Hub")
    c1,c2,c3 = st.columns(3)

    with c1:
        target_csv = target_df().to_csv(index=False).encode()
        st.download_button("Download active target plan", target_csv, "active_target_plan.csv", "text/csv", use_container_width=True)
    with c2:
        actual_csv = actual_df().to_csv(index=False).encode()
        st.download_button("Download all actual data", actual_csv, "actual_snapshots.csv", "text/csv", use_container_width=True)
    with c3:
        gap_csv = gap_df().to_csv(index=False).encode()
        st.download_button("Download gap report", gap_csv, "gap_report.csv", "text/csv", use_container_width=True)

    st.subheader("Backup")
    backup = {
        "saved_plans": st.session_state.saved_plans,
        "actual_rows": st.session_state.actual_rows,
    }
    st.download_button(
        "Download complete app backup",
        json.dumps(backup, indent=2).encode(),
        "ftd_control_center_backup.json",
        "application/json",
    )

    uploaded_backup = st.file_uploader("Restore complete backup", type=["json"])
    if uploaded_backup and st.button("Restore backup"):
        data = json.load(uploaded_backup)
        st.session_state.saved_plans = data.get("saved_plans", {})
        st.session_state.actual_rows = data.get("actual_rows", [])
        st.success("Backup restored. Save plans and actual data to persist.")

elif nav == "⚙️ Settings":
    st.subheader("Settings & Data Format")

    st.markdown("""
### Daily upload format

The app accepts `.xlsx`, `.xls`, or `.csv`.

Minimum recommended columns:

| Column | Meaning |
|---|---|
| Country | Country name |
| Leads | Actual leads |
| FTDs | Actual first-time depositors |
| Marketing Cost | Actual marketing spend |
| NDP | Actual net deposits |

Optional columns:

- Date
- Conversion Rate
- CPL
- CPA
- ROI

The original report format is also supported automatically:

- Row Labels
- Leads
- FTD #
- CR %
- COST
- CPL
- Avg CPA
- ROI
- NDP$
    """)

    if get_supabase():
        st.success("Supabase is configured. Plans and actuals can persist online.")
    else:
        st.warning("Supabase is not configured. Streamlit Cloud may reset local data.")

    st.markdown("""
### Navigation and workflow

1. Create or select a saved plan.
2. Set Target FTDs, CPL, Potential Conversion, and Approval Ratio.
3. CPA recalculates automatically as CPL ÷ (Potential Conversion × Approval Ratio).
4. Save the plan.
5. Upload actual data every day.
6. Open Gap Analysis to compare reality against target.
7. Use Country Drilldown and Plan Comparison for deeper analysis.
    """)
