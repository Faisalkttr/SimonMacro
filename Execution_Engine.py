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
# FETCH DATA
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
# LOAD DATA
# --------------------------------------------------
dxy = fetch(SERIES["DXY"])
y10 = fetch(SERIES["10Y"])
fed = fetch(SERIES["FED"])
rrp = fetch(SERIES["RRP"])
tga = fetch(SERIES["TGA"])
credit_spread = fetch(SERIES["CREDIT_SPREAD"])

# --------------------------------------------------
# ALIGN DATA (CRITICAL FIX)
# --------------------------------------------------
df_liq = pd.concat([fed, rrp, tga], axis=1)
df_liq.columns = ["fed", "rrp", "tga"]
df_liq = df_liq.ffill().dropna()

# --------------------------------------------------
# LIQUIDITY ENGINE (SMOOTHED)
# --------------------------------------------------
net_liquidity = df_liq["fed"] - df_liq["rrp"] - df_liq["tga"]

liq_impulse_raw = net_liquidity.pct_change(30)
liq_impulse = liq_impulse_raw.rolling(5).mean().dropna()

liq_trend = liq_impulse.iloc[-1] if not liq_impulse.empty else 0

# --------------------------------------------------
# CORE SIGNALS
# --------------------------------------------------
yield_trend = y10.pct_change(60).iloc[-1] if not y10.empty else 0
dxy_trend = dxy.pct_change(30).iloc[-1] if not dxy.empty else 0

credit_trend = credit_spread.pct_change(30).rolling(3).mean().dropna()
credit_trend_val = credit_trend.iloc[-1] if not credit_trend.empty else 0

# --------------------------------------------------
# ACTUAL LEVEL VALUES
# --------------------------------------------------
latest_yield = y10.iloc[-1] if not y10.empty else 0
latest_dxy = dxy.iloc[-1] if not dxy.empty else 0
latest_credit = credit_spread.iloc[-1] if not credit_spread.empty else 0
latest_liquidity = net_liquidity.iloc[-1] if not net_liquidity.empty else 0

# --------------------------------------------------
# CREDIT STATE
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
# SYSTEM PHASE
# --------------------------------------------------
def detect_system_phase(liq, dxy, credit):

    if liq < 0 and dxy > 0 and credit == "WIDENING":
        return "FRACTURE"

    if liq < 0 and dxy > 0 and credit == "STRESS SPIKE":
        return "SYSTEM BREAK"

    return "NORMAL"

system_phase = detect_system_phase(liq_trend, dxy_trend, credit_status)

# --------------------------------------------------
# REGIME
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
# SAFER EARLY PIVOT (FILTERED)
# --------------------------------------------------
if liq_trend > 0.01 and yield_trend < 0 and regime == "QT":
    regime = "EARLY_PIVOT"

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
# HELPERS
# --------------------------------------------------
def arrow(x):
    return "↑" if x > 0 else "↓" if x < 0 else "→"

def format_liquidity(x):
    if abs(x) >= 1e12:
        return f"{x/1e12:.2f}T"
    elif abs(x) >= 1e9:
        return f"{x/1e9:.0f}B"
    return f"{x/1e6:.0f}M"

# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------
st.subheader("Macro Chokepoints")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Liquidity",
          format_liquidity(latest_liquidity),
          f"{liq_trend*100:.2f}% {arrow(liq_trend)}")

c2.metric("10Y Yield",
          f"{latest_yield:.2f}%",
          f"{yield_trend*100:.2f}% {arrow(yield_trend)}")

c3.metric("DXY",
          f"{latest_dxy:.2f}",
          f"{dxy_trend*100:.2f}% {arrow(dxy_trend)}")

c4.metric("Credit Spread",
          f"{latest_credit:.2f}%",
          f"{credit_trend_val*100:.2f}% {arrow(credit_trend_val)}")

# --------------------------------------------------
# SYSTEM STATE
# --------------------------------------------------
st.subheader("System State")

c5, c6, c7 = st.columns(3)
c5.metric("Regime", regime)
c6.metric("Credit Condition", credit_status)
c7.metric("System Phase", system_phase)

# --------------------------------------------------
# EXECUTION
# --------------------------------------------------
st.subheader("Execution")

col1, col2 = st.columns(2)
col1.metric("DCA Mode", dca_mode)
col2.metric("Risk Status", "RISK OFF" if system_phase == "SYSTEM BREAK" else "ACTIVE")
