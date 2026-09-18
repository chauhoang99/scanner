from datetime import datetime
import pandas as pd
import requests
import streamlit as st

# Page Configuration & Custom Compact CSS
st.set_page_config(page_title="#TheStrat MTF Monitor (Oanda)", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
    }
    [data-testid="column"] {
        width: 48% !important;
        flex: 1 1 48% !important;
        min-width: unset !important;
        max-width: 48% !important;
        padding: 0px 2px !important;
    }
    table {
        font-size: 10px !important;
        width: 100% !important;
    }
    th, td {
        padding: 3px 4px !important;
        text-align: center !important;
        white-space: nowrap !important;
    }
    th:first-child, td:first-child {
        text-align: left !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# LOAD CREDENTIALS SAFELY FROM STREAMLIT CLOUD SECRETS
# ---------------------------------------------------------
try:
    secret_token = st.secrets.get("oanda_api_token", "")
    secret_account = st.secrets.get("oanda_account_id", "")
    secret_env = st.secrets.get("oanda_env", "Practice")
except Exception:
    secret_token, secret_account, secret_env = "", "", "Practice"

# ---------------------------------------------------------
# SIDEBAR CONFIGURATION
# ---------------------------------------------------------
st.sidebar.header("Oanda API Settings")

env_index = 0 if secret_env == "Practice" else 1
oanda_env = st.sidebar.selectbox("Environment", ["Practice", "Live"], index=env_index)

if secret_token:
    st.sidebar.success("🔒 Oanda Token loaded from Streamlit Secrets")
    api_token = secret_token
    account_id = secret_account
else:
    api_token = st.sidebar.text_input("Oanda API Token", type="password", value="")
    account_id = st.sidebar.text_input("Oanda Account ID", value="")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Strat Settings & Auto-Refresh")

auto_refresh_on = st.sidebar.checkbox("Enable Auto-Refresh", value=False)
refresh_speed = st.sidebar.selectbox(
    "Refresh Interval", ["30 seconds", "1 minute", "5 minutes"], index=1
)

interval_map = {"30 seconds": 30, "1 minute": 60, "5 minutes": 300}
run_interval = interval_map[refresh_speed]

if st.sidebar.button("🔄 Refresh Now"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.subheader("Active Timeframes")
tf_options = {
    "M": ("Month", True),
    "W": ("Week", True),
    "D": ("Day", True),
    "H8": ("8 Hours", True),
    "H1": ("1 Hour", False),
    "M30": ("30 Mins", False),
    "M15": ("15 Mins", False),
    "M5": ("5 Mins", False),
    "M1": ("1 Min", False),
}

selected_tfs = []
for tf_code, (label, default_val) in tf_options.items():
    if st.sidebar.checkbox(f"{tf_code} ({label})", value=default_val):
        selected_tfs.append(tf_code)

# Group Tickers Mapping
group_tickers = {
    "USD": [
        ("EURUSD", "EUR_USD"), ("GBPUSD", "GBP_USD"), ("AUDUSD", "AUD_USD"),
        ("NZDUSD", "NZD_USD"), ("USDCAD", "USD_CAD"), ("USDCHF", "USD_CHF"),
        ("USDJPY", "USD_JPY"), ("USDSGD", "USD_SGD"), ("XAUUSD", "XAU_USD"),
        ("BRENT", "BCO_USD"), ("BTCUSD", "BTC_USD"),
    ],
    "EUR": [
        ("EURUSD", "EUR_USD"), ("EURGBP", "EUR_GBP"), ("EURAUD", "EUR_AUD"),
        ("EURNZD", "EUR_NZD"), ("EURCAD", "EUR_CAD"), ("EURCHF", "EUR_CHF"),
        ("EURJPY", "EUR_JPY"), ("EURSGD", "EUR_SGD"),
    ],
    "GBP": [
        ("GBPUSD", "GBP_USD"), ("EURGBP", "EUR_GBP"), ("GBPAUD", "GBP_AUD"),
        ("GBPNZD", "GBP_NZD"), ("GBPCAD", "GBP_CAD"), ("GBPCHF", "GBP_CHF"),
        ("GBPJPY", "GBP_JPY"), ("GBPSGD", "GBP_SGD"),
    ],
    "AUD": [
        ("AUDUSD", "AUD_USD"), ("EURAUD", "EUR_AUD"), ("GBPAUD", "GBP_AUD"),
        ("AUDNZD", "AUD_NZD"), ("AUDCAD", "AUD_CAD"), ("AUDCHF", "AUD_CHF"),
        ("AUDJPY", "AUD_JPY"), ("AUDSGD", "AUD_SGD"), ("XAUUSD", "XAU_USD"),
    ],
    "CAD": [
        ("EURCAD", "EUR_CAD"), ("GBPCAD", "GBP_CAD"), ("AUDCAD", "AUD_CAD"),
        ("USDCAD", "USD_CAD"), ("CADCHF", "CAD_CHF"), ("CADJPY", "CAD_JPY"),
        ("BRENT", "BCO_USD"),
    ],
    "NZD": [
        ("NZDUSD", "NZD_USD"), ("EURNZD", "EUR_NZD"), ("GBPNZD", "GBP_NZD"),
        ("AUDNZD", "AUD_NZD"), ("NZDCAD", "NZD_CAD"), ("NZDCHF", "NZD_CHF"),
    ],
    "JPY": [
        ("EURJPY", "EUR_JPY"), ("GBPJPY", "GBP_JPY"), ("AUDJPY", "AUD_JPY"),
        ("NZDJPY", "NZD_JPY"), ("USDJPY", "USD_JPY"), ("CADJPY", "CAD_JPY"),
    ],
    "CHF": [
        ("EURCHF", "EUR_CHF"), ("GBPCHF", "GBP_CHF"), ("AUDCHF", "AUD_CHF"),
        ("NZDCHF", "NZD_CHF"), ("USDCHF", "USD_CHF"), ("CADCHF", "CAD_CHF"),
    ],
    "SGD": [
        ("EURSGD", "EUR_SGD"), ("GBPSGD", "GBP_SGD"), ("AUDSGD", "AUD_SGD"),
        ("NZDSGD", "NZD_SGD"), ("USDSGD", "USD_SGD"), ("CADSGD", "CAD_SGD"),
    ],
}


# ---------------------------------------------------------
# OANDA CANDLE FETCH FUNCTION
# ---------------------------------------------------------
def fetch_oanda_candles(instrument, granularity, count=3, token=None, env="Practice"):
    if not token:
        return None

    domain = "api-fxtrade.oanda.com" if env == "Live" else "api-fxpractice.oanda.com"
    url = f"https://{domain}/v3/instruments/{instrument}/candles"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    params = {
        "price": "M",
        "granularity": granularity,
        "count": count
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            candles = response.json().get("candles", [])
            valid_candles = [c for c in candles if c.get("complete") or c == candles[-1]]
            if len(valid_candles) >= 2:
                c1 = valid_candles[-2]["mid"]  # 1 bar ago (Closed)
                c0 = valid_candles[-1]["mid"]  # Live opening bar
                return {
                    "c1_high": float(c1["h"]),
                    "c1_low": float(c1["l"]),
                    "c0_open": float(c0["o"]),
                    "c0_high": float(c0["h"]),
                    "c0_low": float(c0["l"]),
                    "c0_close": float(c0["c"]),
                }
    except Exception:
        return None
    return None


# ---------------------------------------------------------
# UNIFIED STRAT ANALYSIS ENGINE
# ---------------------------------------------------------
def analyze_single_bar(o, h, l, c, prev_h, prev_l):
    higher_high = h > prev_h
    lower_low = l < prev_l

    # 1. Strat Candle Structure Type
    if higher_high and lower_low:
        num = "3"
    elif higher_high and not lower_low:
        num = "2U"
    elif not higher_high and lower_low:
        num = "2D"
    else:
        num = "1"

    # 2. Candle Color Arrow
    arrow = "↑" if c >= o else "↓"

    # 3. In-Force Range Holding Condition
    in_force_up = c > prev_h
    in_force_dn = c < prev_l

    if in_force_up:
        triangle = "▲"
    elif in_force_dn:
        triangle = "▼"
    else:
        triangle = ""

    # Universal Output Formatting: [Type] [Arrow] [Triangle]
    state = f"{num} {arrow} {triangle}".strip()

    return {
        "status": state,
        "in_force_up": in_force_up,
        "in_force_dn": in_force_dn
    }


# ---------------------------------------------------------
# ROW STYLING FUNCTION
# ---------------------------------------------------------
def style_row(row):
    styles = [""] * len(row)
    for i, col in enumerate(row.index):
        val_clean = str(row[col]).strip()

        if "2U" in val_clean:
            if "↓" in val_clean:
                styles[i] = "background-color: #f77c80; color: black; font-weight: bold;"  # 2U Red (Muted Red/Pink)
            else:
                styles[i] = "background-color: #4caf50; color: white; font-weight: bold;"  # 2U Green (Bright Green)
        elif "2D" in val_clean:
            if "↑" in val_clean:
                styles[i] = "background-color: #81c784; color: black; font-weight: bold;"  # 2D Green (Light Green)
            else:
                styles[i] = "background-color: #f23645; color: white; font-weight: bold;"  # 2D Red (Bright Red)
        elif val_clean.startswith("1"):
            if "↑" in val_clean:
                styles[i] = "background-color: #ffeb3b; color: black; font-weight: bold;"  # 1 Up (Yellow)
            else:
                styles[i] = "background-color: #ff9800; color: black; font-weight: bold;"  # 1 Down (Orange)
        elif val_clean.startswith("3"):
            if "↑" in val_clean:
                styles[i] = "background-color: #1b5e20; color: white; font-weight: bold;"  # 3 Up (Dark Green)
            else:
                styles[i] = "background-color: #801922; color: white; font-weight: bold;"  # 3 Down (Dark Red)
        elif "In Force" in val_clean or "Conflicted" in val_clean or "None" in val_clean:
            if "▲" in val_clean:
                styles[i] = "color: #4caf50; font-weight: bold;"
            elif "▼" in val_clean:
                styles[i] = "color: #f23645; font-weight: bold;"
            elif "Conflicted" in val_clean:
                styles[i] = "color: #ff9800; font-weight: bold;"
            else:
                styles[i] = "color: #808080;"
    return styles


def get_group_strat_df(tickers_to_scan, candle_cache):
    results = []
    if not api_token:
        return pd.DataFrame([{"Ticker": "Missing Token", "Status": "Check Secrets"}])

    for display_name, oanda_inst in tickers_to_scan:
        row_data = {"Ticker": display_name}
        up_count = 0
        dn_count = 0

        for tf in selected_tfs:
            data = candle_cache.get((oanda_inst, tf))
            if data:
                # Live Candle (C0 evaluated vs C1)
                curr_res = analyze_single_bar(
                    data["c0_open"], data["c0_high"], data["c0_low"], data["c0_close"],
                    data["c1_high"], data["c1_low"]
                )

                row_data[tf] = curr_res["status"]

                if curr_res["in_force_up"]: up_count += 1
                if curr_res["in_force_dn"]: dn_count += 1
            else:
                row_data[tf] = "N/A"

        # In-Force Summary
        if up_count > 0 and dn_count > 0:
            row_data["Summary"] = "Conflicted"
        elif up_count > 0:
            row_data["Summary"] = f"{up_count} ▲ In Force"
        elif dn_count > 0:
            row_data["Summary"] = f"{dn_count} ▼ In Force"
        else:
            row_data["Summary"] = "None"

        results.append(row_data)

    return pd.DataFrame(results)


# ---------------------------------------------------------
# DASHBOARD RENDERING FRAGMENT
# ---------------------------------------------------------
active_refresh_rate = run_interval if auto_refresh_on else None

@st.fragment(run_every=active_refresh_rate)
def render_strat_dashboard():
    if not api_token:
        st.warning("⚠️ Oanda API token not found. Please add `oanda_api_token` to your Streamlit Cloud Secrets dashboard.")
        return

    unique_instruments = sorted(list({oanda_inst for group in group_tickers.values() for _, oanda_inst in group}))

    candle_cache = {}
    with st.spinner("Fetching live Oanda Strat data..."):
        for inst in unique_instruments:
            for tf in selected_tfs:
                candle_cache[(inst, tf)] = fetch_oanda_candles(
                    inst, tf, count=3, token=api_token, env=oanda_env
                )

    st.caption(f"⏱️ **Active Strat State** | Last updated: {datetime.now().strftime('%H:%M:%S')}")

    group_items = list(group_tickers.items())

    for i in range(0, len(group_items), 2):
        cols = st.columns(2)

        with cols[0]:
            g_name_1, t_list_1 = group_items[i]
            st.markdown(f"##### 💱 {g_name_1} Group")
            df_1 = get_group_strat_df(t_list_1, candle_cache)
            if not df_1.empty:
                st.table(df_1.style.apply(style_row, axis=1))

        if i + 1 < len(group_items):
            with cols[1]:
                g_name_2, t_list_2 = group_items[i + 1]
                st.markdown(f"##### 💱 {g_name_2} Group")
                df_2 = get_group_strat_df(t_list_2, candle_cache)
                if not df_2.empty:
                    st.table(df_2.style.apply(style_row, axis=1))

        st.markdown("---")


render_strat_dashboard()
