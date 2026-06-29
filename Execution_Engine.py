import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(page_title="Sovereign Macro Engine", layout="wide")
st.title("Sovereign Macro Execution Engine")
st.caption("Execution > Prediction | Survival First")

# --------------------------------------------------
# API CONFIG
# --------------------------------------------------
api_key = st.secrets.get("FRED_API_KEY")
if not api_key:
    api_key = st.sidebar.text_input("Enter FRED API Key", type="password")

if not api_key:
    st.warning("Enter FRED API Key")
    st.stop()

start_date = "2015-01-01"
end_date = datetime.now().strftime("%Y-%m-%d")

# --------------------------------------------------
# SERIES MAP
# --------------------------------------------------
SERIES = {
    "DXY": "DTWEXAFEGS",
    "10Y": "DGS10",
    "FED": "WALCL",
    "RRP": "RRPONTSYD",
    "TGA": "WTREGEN",
    "CREDIT_SPREAD": "BAMLH0A0HYM2"
}

# --------------------------------------------------
# FETCH FUNCTION (CRITICAL FIX)
# --------------------------------------------------
@st.cache_data(ttl=86400)
def fetch(series):
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start_date,
        "observation_end": end_date
    }

    try:
        r = requests.get(url, params=params)
        data = r.json()

        if "observations" not in data:
            return pd.Series(dtype="float64")

        df = pd.DataFrame(data["observations"])
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")

        return df.dropna().set_index("date")["value"]

    except:
        return pd.Series(dtype="float64")

# --------------------------------------------------
# FETCH DATA
# --------------------------------------------------
dxy = fetch(SERIES["DXY"])
y10 = fetch(SERIES["10Y"])
fed = fetch(SERIES["FED"])
rrp = fetch(SERIES["RRP"])
tga = fetch(SERIES["TGA"])
credit_spread = fetch(SERIES["CREDIT_SPREAD"])

if dxy.empty or y10.empty:
    st.error("Critical data missing")
    st.stop()

# --------------------------------------------------
# LIQUIDITY ENGINE
# --------------------------------------------------
net_liquidity = fed - rrp - tga
liquidity_impulse = net_liquidity.pct_change(30).dropna()
liq_trend = liquidity_impulse.iloc[-1] if not liquidity_impulse.empty else 0

# --------------------------------------------------
# CORE SIGNALS
# --------------------------------------------------
yield_trend = y10.pct_change(60).iloc[-1] if not y10.empty else 0
dxy_trend = dxy.pct_change(30).iloc[-1] if not dxy.empty else 0

credit_trend = credit_spread.pct_change(30).dropna()
credit_trend_val = credit_trend.iloc[-1] if not credit_trend.empty else 0

# --------------------------------------------------
# ✅ ACTUAL LEVEL VALUES
# --------------------------------------------------
latest_yield = y10.iloc[-1] if not y10.empty else 0
latest_dxy = dxy.iloc[-1] if not dxy.empty else 0
latest_credit = credit_spread.iloc[-1] if not credit_spread.empty else 0
latest_liquidity = net_liquidity.iloc[-1] if not net_liquidity.empty else 0

# --------------------------------------------------
# CREDIT STATE (EDGE)
# --------------------------------------------------
def credit_state(val):
    if val > 0.15:
        return "STRESS SPIKE"
    elif val > 0:
        return "WIDENING"
    else:
        return "STABLE"

credit_status = credit_state(credit_trend_val)

# --------------------------------------------------
# SYSTEM PHASE DETECTION (KEY EDGE)
# --------------------------------------------------
def detect_system_phase(liq, dxy, credit):

    if liq < 0 and dxy > 0 and credit == "WIDENING":
        return "FRACTURE"

    if liq < 0 and dxy > 0 and credit == "STRESS SPIKE":
        return "SYSTEM BREAK"

    return "NORMAL"

system_phase = detect_system_phase(liq_trend, dxy_trend, credit_status)

# --------------------------------------------------
# REGIME CLASSIFICATION
# --------------------------------------------------
def classify_regime(y, d):
    if y > 0 and d > 0:
        return "QT"
    elif y < 0 and d < 0:
        return "SOFT_PIVOT"
    elif y < 0 and d > 0:
        return "HARD_PIVOT"
    else:
        return "TRANSITION"

regime = classify_regime(yield_trend, dxy_trend)

# --------------------------------------------------
# LIQUIDITY OVERRIDE
# --------------------------------------------------
if liq_trend > 0 and regime == "QT":
    regime = "EARLY_PIVOT"
elif liq_trend < 0 and regime != "QT":
    regime = "HIDDEN_TIGHTENING"

# --------------------------------------------------
# BASE ALLOCATION
# --------------------------------------------------
ALLOCATIONS = {
    "QT": {"BTC":20,"Gold":15,"Energy":25,"Materials":15,"Infra":10,"AI":5,"EM":5,"Cash":5},
    "SOFT_PIVOT": {"BTC":30,"Gold":10,"Energy":20,"Materials":10,"Infra":10,"AI":10,"EM":5,"Cash":5},
    "HARD_PIVOT": {"BTC":40,"Gold":5,"Energy":15,"Materials":10,"Infra":10,"AI":15,"EM":2,"Cash":3},
    "EARLY_PIVOT": {"BTC":35,"Gold":8,"Energy":18,"Materials":10,"Infra":10,"AI":12,"EM":4,"Cash":3},
    "HIDDEN_TIGHTENING": {"BTC":20,"Gold":20,"Energy":20,"Materials":10,"Infra":10,"AI":5,"EM":5,"Cash":10}
}

allocation = ALLOCATIONS.get(regime, ALLOCATIONS["QT"]).copy()

# --------------------------------------------------
# SYSTEM BREAK SAFETY
# --------------------------------------------------
risk_kill = False
if system_phase == "SYSTEM BREAK":
    risk_kill = True

if risk_kill:
    allocation = {
        "BTC": 20,
        "Gold": 25,
        "Cash": 30,
        "Defensive": 25
    }

# --------------------------------------------------
# NORMALIZE
# --------------------------------------------------
total = sum(allocation.values())
allocation = {k: round(v / total * 100, 2) for k, v in allocation.items()}

# --------------------------------------------------
# DCA LOGIC
# --------------------------------------------------
if liq_trend > 0.05:
    dca_mode = "HIGH DCA"
elif liq_trend > 0:
    dca_mode = "MEDIUM DCA"
else:
    dca_mode = "LOW / PAUSE"

# --------------------------------------------------
# UI HELPERS
# --------------------------------------------------
def arrow(x):
    if x > 0: return "↑"
    if x < 0: return "↓"
    return "→"

# --------------------------------------------------
# CHOKEPOINT DASHBOARD (CORE FEATURE)
# --------------------------------------------------
st.subheader("Macro Chokepoints")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Liquidity",
    f"{latest_liquidity/1e12:.2f}T",
    f"{liq_trend*100:.2f}% {arrow(liq_trend)}"
)

c2.metric(
    "10Y Yield",
    f"{latest_yield:.2f}%",
    f"{yield_trend*100:.2f}% {arrow(yield_trend)}"
)

c3.metric(
    "DXY",
    f"{latest_dxy:.2f}",
    f"{dxy_trend*100:.2f}% {arrow(dxy_trend)}"
)

c4.metric(
    "Credit Spread",
    f"{latest_credit:.2f}%",
    f"{credit_trend_val*100:.2f}% {arrow(credit_trend_val)}"
)

# --------------------------------------------------
# SYSTEM STATE
# --------------------------------------------------
st.subheader("System State")

c5, c6, c7 = st.columns(3)
c5.metric("Regime", regime)
c6.metric("Credit Condition", credit_status)
c7.metric("System Phase", system_phase)

# --------------------------------------------------
# EXECUTION OUTPUT
# --------------------------------------------------
st.subheader("Execution")

col1, col2 = st.columns(2)
col1.metric("DCA Mode", dca_mode)
col2.metric("Risk Status", "RISK OFF" if risk_kill else "ACTIVE")

st.subheader("Target Allocation")
st.dataframe(pd.DataFrame.from_dict(allocation, orient="index", columns=["%"]))

if risk_kill:
    st.error("⚠️ SYSTEM BREAK DETECTED — CAPITAL PRESERVATION MODE")
