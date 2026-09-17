import streamlit as st
import requests
import pandas as pd

# ==============================================================================
# 1. CONFIGURATION & CONSTANTS
# ==============================================================================
st.set_page_config(page_title="TheStrat MTF Monitor", layout="wide")

DEFAULT_TIMEFRAMES = ["M", "W", "D", "H8", "M30", "M15", "M10", "M5", "M1"]
MAJOR_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]

# ==============================================================================
# 2. SECRETS & CREDENTIALS RETRIEVAL
# ==============================================================================
# Primary: Streamlit Community Cloud secrets (st.secrets)
# Secondary: Sidebar inputs for local fallback
api_key = st.secrets.get("OANDA_API_KEY")
account_id = st.secrets.get("OANDA_ACCOUNT_ID")
environment = st.secrets.get("OANDA_ENV", "Practice")

if not api_key or not account_id:
    st.sidebar.header("🔑 Manual OANDA Credentials")
    st.sidebar.info("Secrets not detected in Streamlit Cloud. Please enter them manually below.")
    api_key = api_key or st.sidebar.text_input("API Access Token", type="password")
    account_id = account_id or st.sidebar.text_input("Account ID")
    environment = st.sidebar.selectbox("Environment", ["Practice", "Live"], index=0 if environment == "Practice" else 1)
else:
    st.sidebar.success(f"🔒 Authenticated via Cloud Secrets ({environment} Mode)")

# ==============================================================================
# 3. OANDA API HELPERS
# ==============================================================================
def get_oanda_headers(key):
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}"
    }

def get_oanda_base_url(env):
    return "https://api-fxpractice.oanda.com" if env == "Practice" else "https://api-fxtrade.oanda.com"

@st.cache_data(ttl=3600)
def fetch_forex_pairs(key, acc_id, env):
    """Fetch all available currency pairs from OANDA."""
    url = f"{get_oanda_base_url(env)}/v3/accounts/{acc_id}/instruments"
    try:
        resp = requests.get(url, headers=get_oanda_headers(key), timeout=10)
        if resp.status_code == 200:
            instruments = resp.json().get("instruments", [])
            pairs = [inst["name"] for inst in instruments if inst.get("type") == "CURRENCY"]
            return sorted(pairs)
        else:
            st.error(f"Failed to fetch pairs: {resp.text}")
            return []
    except Exception as e:
        st.error(f"API Connection Error: {e}")
        return []

def fetch_candle_data(pair, granularity, key, env):
    """Fetch latest candles for a given pair and granularity."""
    url = f"{get_oanda_base_url(env)}/v3/instruments/{pair}/candles"
    params = {"count": 3, "granularity": granularity, "price": "M"}
    try:
        resp = requests.get(url, headers=get_oanda_headers(key), params=params, timeout=5)
        if resp.status_code == 200:
            candles = resp.json().get("candles", [])
            valid_candles = [c for c in candles if c.get("complete") or c == candles[-1]]
            if len(valid_candles) >= 2:
                prev_c = valid_candles[-2]["mid"]
                curr_c = valid_candles[-1]["mid"]
                return {
                    "open": float(curr_c["o"]),
                    "high": float(curr_c["h"]),
                    "low": float(curr_c["l"]),
                    "close": float(curr_c["c"]),
                    "prev_high": float(prev_c["h"]),
                    "prev_low": float(prev_c["l"]),
                    "prev_open": float(prev_c["o"])
                }
    except Exception:
        pass
    return None

# ==============================================================================
# 4. THE STRAT LOGIC ENGINE
# ==============================================================================
def get_strat_bar_type(h, l, prev_h, prev_l):
    if h > prev_h and l < prev_l:
        return "3"
    elif h > prev_h and l >= prev_l:
        return "2U"
    elif l < prev_l and h <= prev_h:
        return "2D"
    elif h <= prev_h and l >= prev_l:
        return "1"
    return "?"

def analyze_tf_strat(o, h, l, c, prev_h, prev_l, failed_method="Either"):
    bar_type = get_strat_bar_type(h, l, prev_h, prev_l)
    above_open = c > o
    inside_prev_range = (c <= prev_h) and (c >= prev_l)

    # Failed 2 Evaluation
    is_f2u, is_f2d = False, False
    if bar_type == "2U":
        if failed_method == "Open": is_f2u = not above_open
        elif failed_method == "Reclaim": is_f2u = inside_prev_range
        elif failed_method == "Both": is_f2u = (not above_open) and inside_prev_range
        elif failed_method == "Either": is_f2u = (not above_open) or inside_prev_range
    elif bar_type == "2D":
        if failed_method == "Open": is_f2d = above_open
        elif failed_method == "Reclaim": is_f2d = inside_prev_range
        elif failed_method == "Both": is_f2d = above_open and inside_prev_range
        elif failed_method == "Either": is_f2d = above_open or inside_prev_range

    is_failed = is_f2u or is_f2d

    # In Force Status
    in_force_up = c > prev_h
    in_force_dn = c < prev_l

    # Style / Color assignment
    if bar_type == "1":
        color = "#ffeb3b" if above_open else "#ff9800"
    elif bar_type == "2U":
        color = "#f77c80" if is_failed else "#4caf50"
    elif bar_type == "2D":
        color = "#81c784" if is_failed else "#f23645"
    elif bar_type == "3":
        color = "#1b5e20" if above_open else "#801922"
    else:
        color = "#808080"

    in_force_str = "▲" if in_force_up else ("▼" if in_force_dn else "")
    dir_str = "↑" if above_open else "↓"
    status_str = f"{bar_type} {'F' if is_failed else ''} {dir_str} {in_force_str}".strip()

    return {
        "status": status_str,
        "color": color,
        "in_force_up": in_force_up,
        "in_force_dn": in_force_dn
    }

# ==============================================================================
# 5. STREAMLIT INTERFACE & RUNTIME
# ==============================================================================
st.title("📊 #TheStrat Multi-Timeframe Dashboard (OANDA)")

if not api_key or not account_id:
    st.warning("⚠️ Credentials missing. Please enter them in Streamlit Cloud Secrets or in the sidebar.")
    st.stop()

# Sidebar Setup Options
st.sidebar.header("⚙️ Strategy Settings")
failed_method = st.sidebar.selectbox("Failed 2 Method", ["Either", "Open", "Reclaim", "Both"])
selected_tfs = st.sidebar.multiselect("Active Timeframes", DEFAULT_TIMEFRAMES, default=["M", "W", "D", "H8", "M30", "M15"])

# Load Available Instruments
all_pairs = fetch_forex_pairs(api_key, account_id, environment)

if not all_pairs:
    st.info("No forex pairs found. Please check your API key and Account ID.")
    st.stop()

# Grouping Selection
st.sidebar.header("📌 Currency Grouping")
currency_group = st.sidebar.selectbox("Filter by Main Currency", ["ALL"] + MAJOR_CURRENCIES)

filtered_pairs = all_pairs
if currency_group != "ALL":
    filtered_pairs = [p for p in all_pairs if currency_group in p.split("_")]

if st.button("🔄 Fetch & Update Market Data") or "strat_data" not in st.session_state:
    st.session_state.strat_data = {}
    progress_bar = st.progress(0)
    
    for idx, pair in enumerate(filtered_pairs):
        pair_results = {}
        for tf in selected_tfs:
            data = fetch_candle_data(pair, tf, api_key, environment)
            if data:
                res = analyze_tf_strat(
                    data["open"], data["high"], data["low"], data["close"],
                    data["prev_high"], data["prev_low"], failed_method
                )
                pair_results[tf] = res
        st.session_state.strat_data[pair] = pair_results
        progress_bar.progress((idx + 1) / len(filtered_pairs))
    progress_bar.empty()

# Display Results Dataframe
if st.session_state.strat_data:
    st.subheader(f"Results for {currency_group} Pairs ({len(filtered_pairs)} instruments)")
    
    table_rows = []
    for pair in filtered_pairs:
        row_data = {"Pair": pair.replace("_", "/")}
        tf_data_map = st.session_state.strat_data.get(pair, {})
        
        up_count = sum(1 for tf_info in tf_data_map.values() if tf_info.get("in_force_up"))
        dn_count = sum(1 for tf_info in tf_data_map.values() if tf_info.get("in_force_dn"))
        
        for tf in selected_tfs:
            tf_info = tf_data_map.get(tf)
            row_data[tf] = tf_info["status"] if tf_info else "N/A"
            
        if up_count > 0 and dn_count > 0:
            row_data["In-Force Summary"] = "Conflicted"
        elif up_count > 0:
            row_data["In-Force Summary"] = f"{up_count} ▲ In Force"
        elif dn_count > 0:
            row_data["In-Force Summary"] = f"{dn_count} ▼ In Force"
        else:
            row_data["In-Force Summary"] = "None"
            
        table_rows.append(row_data)

    df = pd.DataFrame(table_rows)
    st.dataframe(df, use_container_width=True, height=600)
