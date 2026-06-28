import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(page_title="Sovereign DCA Engine", layout="wide")
st.title("Sovereign Macro Execution Engine")
st.caption("Execution > Prediction | Survival First")

# --------------------------------------------------
# API CONFIG
# --------------------------------------------------

api_key = st.secrets.get("FRED_API_KEY")

if not api_key:
    api_key = st.sidebar.text_input("Enter FRED API Key", type="password")


start_date = "2018-01-01"
end_date = datetime.now().strftime("%Y-%m-%d")

# --------------------------------------------------
# SERIES MAP (UPDATED TO MATCH YOUR SYSTEM)
# --------------------------------------------------
SERIES = {
    "DXY": "DTWEXAFEGS",
    "10Y": "DGS10",
    "FED": "WALCL",
    "RRP": "RRPONTSYD",
    "TGA": "WTREGEN",
    "CREDIT": "TOTLL"
}

# --------------------------------------------------
# DATA FETCH
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

        # ✅ IMPORTANT: check if data exists
        if "observations" not in data:
            st.error(f"Error loading data for {series}. Check API key.")
            return pd.Series()

        df = pd.DataFrame(data["observations"])

        if df.empty:
            st.warning(f"No data for {series}")
            return pd.Series()

        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")

        return df.dropna().set_index("date")["value"]

    except Exception as e:
        st.error(f"Failed to load {series}")
        return pd.Series()

# --------------------------------------------------
# FETCH DATA
# --------------------------------------------------
if not api_key:
    st.warning("Enter FRED API Key")
    st.stop()

dxy = fetch(SERIES["DXY"])
y10 = fetch(SERIES["10Y"])
fed = fetch(SERIES["FED"])
rrp = fetch(SERIES["RRP"])
tga = fetch(SERIES["TGA"])
credit = fetch(SERIES["CREDIT"])

# --------------------------------------------------
# LIQUIDITY ENGINE (YOUR EDGE)
# --------------------------------------------------
net_liquidity = fed - rrp - tga

liquidity_impulse = net_liquidity.pct_change(30).dropna()

# ✅ DEFINE IT ONCE HERE
liq_trend = liquidity_impulse.iloc[-1] if not liquidity_impulse.empty else 0


# --------------------------------------------------
# REGIME CLASSIFICATION (YOUR RULEBOOK)
# --------------------------------------------------
def classify_regime(yield_series, dxy_series):
    y = yield_series.pct_change(60).iloc[-1]
    u = dxy_series.pct_change(60).iloc[-1]

    if y > 0 and u > 0:
        return "QT"
    elif y < 0 and u < 0:
        return "SOFT_PIVOT"
    elif y < 0 and u > 0:
        return "HARD_PIVOT"
    else:
        return "TRANSITION"

regime = classify_regime(y10, dxy)

# --------------------------------------------------
# LIQUIDITY OVERRIDE (FRONT-RUN)
# --------------------------------------------------
if liq_trend > 0 and regime == "QT":
    regime = "EARLY_PIVOT"
elif liq_trend < 0 and regime != "QT":
    regime = "HIDDEN_TIGHTENING"
# --------------------------------------------------
# BASE ALLOCATION (FROM YOUR RULEBOOK)
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
# CONDITIONS (SIMPLIFIED INPUTS)
# --------------------------------------------------
btc_drawdown = st.sidebar.slider("BTC Drawdown (%)", -80, 0, -20)
ai_hype = st.sidebar.checkbox("AI Euphoric")
euphoria = st.sidebar.checkbox("Market Euphoria")
crash = st.sidebar.checkbox("Market Crash")

# --------------------------------------------------
# IF-THEN EXECUTION ENGINE
# --------------------------------------------------
if btc_drawdown <= -30:
    allocation["BTC"] += 10

if ai_hype:
    allocation["AI"] -= 5
    allocation["Cash"] += 5

if euphoria:
    for k in allocation:
        if k != "Cash":
            allocation[k] *= 0.9
    allocation["Cash"] += 10

if crash:
    allocation["BTC"] += 10
    allocation["Energy"] += 5

# --------------------------------------------------
# RISK KILL SWITCH (SURVIVAL FIRST)
# --------------------------------------------------
credit_trend = credit.pct_change(30).iloc[-1]
dxy_trend = dxy.pct_change(30).iloc[-1]
liq_trend = liquidity_impulse.iloc[-1]

risk_kill = False

if (dxy_trend > 0) and (liq_trend < 0) and (credit_trend < 0):
    risk_kill = True

if risk_kill:
    allocation = {
        "BTC": 20,
        "Gold": 20,
        "Cash": 30,
        "Defensive": 30
    }

# --------------------------------------------------
# NORMALIZE TO 100%
# --------------------------------------------------
total = sum(allocation.values())
allocation = {k: round(v / total * 100, 2) for k, v in allocation.items()}

# --------------------------------------------------
# DCA SCALING
# --------------------------------------------------
if liq_trend > 0.05:
    dca_mode = "HIGH DCA"
elif liq_trend > 0:
    dca_mode = "MEDIUM DCA"
else:
    dca_mode = "LOW / PAUSE"

# --------------------------------------------------
# OUTPUT
# --------------------------------------------------
col1, col2, col3 = st.columns(3)

col1.metric("Regime", regime)
col2.metric("Liquidity Trend", f"{round(liq_trend*100,2)}%")
col3.metric("DCA Mode", dca_mode)

st.subheader("Target Allocation")
st.dataframe(pd.DataFrame.from_dict(allocation, orient="index", columns=["%"]))

if risk_kill:
    st.error("⚠️ RISK OFF: SYSTEM PROTECTION ACTIVE")
