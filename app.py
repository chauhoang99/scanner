from datetime import datetime, timedelta
import re
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

# Page Configuration
st.set_page_config(page_title="Scanner", layout="wide")

# Custom CSS to force 2 columns side-by-side on mobile and shrink table elements
st.markdown(
    """
    <style>
    /* Force Streamlit columns to stay side-by-side on mobile screens */
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
    
    /* Shrink table font size and padding to fit two per row */
    table {
        font-size: 8px !important;
        width: 100% !important;
    }
    th, td {
        padding: 1px 2px !important;
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
# SIDEBAR CONFIGURATION
# ---------------------------------------------------------
st.sidebar.header("Scanner Settings")

trend_mode = st.sidebar.selectbox(
    "Trend Mode",
    ["Open, High, Low, Close + Midline", "Above/Below Midline"],
    help=(
        "Choose between detailed OHLC candle scoring or simple"
        " Above/Below Midline scoring."
    ),
)

st.sidebar.subheader("Auto-Refresh Settings")
auto_refresh_on = st.sidebar.checkbox("Enable Auto-Refresh", value=False)
refresh_speed = st.sidebar.selectbox(
    "Refresh Interval", ["10 seconds", "30 seconds", "1 minute", "5 minutes"], index=1
)

interval_map = {
    "10 seconds": 10,
    "30 seconds": 30,
    "1 minute": 60,
    "5 minutes": 300,
}
run_interval = interval_map[refresh_speed] if auto_refresh_on else None

if st.sidebar.button("🔄 Refresh Now"):
  st.rerun()

st.sidebar.subheader("Timeframes to Scan")
available_timeframes = ["60m", "1d", "1wk", "1mo", "3mo", "1y"]

tf1_on = st.sidebar.checkbox("Timeframe #1 On/Off", value=True)
tf1 = st.sidebar.selectbox("Timeframe #1", available_timeframes, index=1)

tf2_on = st.sidebar.checkbox("Timeframe #2 On/Off", value=True)
tf2 = st.sidebar.selectbox("Timeframe #2", available_timeframes, index=2)

tf3_on = st.sidebar.checkbox("Timeframe #3 On/Off", value=True)
tf3 = st.sidebar.selectbox("Timeframe #3", available_timeframes, index=3)

tf4_on = st.sidebar.checkbox("Timeframe #4 On/Off", value=True)
tf4 = st.sidebar.selectbox("Timeframe #4", available_timeframes, index=4)

# Define Tickers per group (matching OANDA FX pairs from Pine Script)
group_tickers = {
    "USD": [
        ("EURUSD", "EURUSD=X", True),
        ("GBPUSD", "GBPUSD=X", True),
        ("AUDUSD", "AUDUSD=X", True),
        ("NZDUSD", "NZDUSD=X", True),
        ("USDCAD", "USDCAD=X", False),
        ("USDCHF", "USDCHF=X", False),
        ("USDJPY", "USDJPY=X", False),
        ("USDSGD", "USDSGD=X", False),
        ("XAUUSD", "GC=F"    , True),
        ("BRENT",  "BZ=F"    , False),
        ("US30",   "ZB=F"    , True),
        ("BTCUSD", "BTC-USD" , True),
    ],
    "EUR": [
        ("EURUSD", "EURUSD=X", False),
        ("EURGBP", "EURGBP=X", False),
        ("EURAUD", "EURAUD=X", False),
        ("EURNZD", "EURNZD=X", False),
        ("EURCAD", "EURCAD=X", False),
        ("EURCHF", "EURCHF=X", False),
        ("EURJPY", "EURJPY=X", False),
        ("EURSGD", "EURSGD=X", False),
        ("XAUEUR", "XAUEUR=X", True)
    ],
    "GBP": [
        ("GBPUSD", "GBPUSD=X", False),
        ("EURGBP", "EURGBP=X", True),
        ("GBPAUD", "GBPAUD=X", False),
        ("GBPNZD", "GBPNZD=X", False),
        ("GBPCAD", "GBPCAD=X", False),
        ("GBPCHF", "GBPCHF=X", False),
        ("GBPJPY", "GBPJPY=X", False),
        ("GBPSGD", "GBPSGD=X", False),
        ("UK10Y" , "IGLT.L"  , True)
    ],
    "AUD": [
        ("AUDUSD", "AUDUSD=X", False),
        ("EURAUD", "EURAUD=X", True),
        ("GBPAUD", "GBPAUD=X", True),
        ("AUDNZD", "AUDNZD=X", False),
        ("AUDCAD", "AUDCAD=X", False),
        ("AUDCHF", "AUDCHF=X", False),
        ("AUDJPY", "AUDJPY=X", False),
        ("AUDSGD", "AUDSGD=X", False),
        ("XAUUSD", "GC=F"    , False),
        ("VGB"   , "VGB.AX"  , True)
    ],
    "CAD": [
        ("EURCAD", "EURCAD=X", True),
        ("GBPCAD", "GBPCAD=X", True),
        ("AUDCAD", "AUDCAD=X", True),
        ("USDCAD", "USDCAD=X", True),
        ("CADCHF", "CADCHF=X", False),
        ("CADJPY", "CADJPY=X", False),
        ("BRENT" , "BZ=F"    , False),
        ("VAB"   , "VAB.TO"  , True ),
    ],
    "NZD": [
        ("NZDUSD", "NZDUSD=X", False),
        ("EURNZD", "EURNZD=X", True),
        ("GBPNZD", "GBPNZD=X", True),
        ("AUDNZD", "AUDNZD=X", True),
        ("NZDCAD", "NZDCAD=X", False),
        ("NZDCHF", "NZDCHF=X", False),
        ("NGB"   , "NGB.NZ"  , True),
    ],
    "JPY": [
        ("EURJPY", "EURJPY=X", True),
        ("GBPJPY", "GBPJPY=X", True),
        ("AUDJPY", "AUDJPY=X", True),
        ("NZDJPY", "NZDJPY=X", True),
        ("USDJPY", "USDJPY=X", True),
        ("CADJPY", "CADJPY=X", True),
        ("JGB"   , "2561.T"  , True)
    ],
    "CHF": [
        ("EURCHF", "EURCHF=X", True),
        ("GBPCHF", "GBPCHF=X", True),
        ("AUDCHF", "AUDCHF=X", True),
        ("NZDCHF", "NZDCHF=X", True),
        ("USDCHF", "USDCHF=X", True),
        ("CADCHF", "CADCHF=X", True),
        ("XAUUSD", "GC=F"    , False),
        ("CSBGC" , "CSBGC0.SW", True)
    ],
    "SGD": [
        ("EURSGD", "EURSGD=X", True),
        ("GBPSGD", "GBPSGD=X", True),
        ("AUDSGD", "AUDSGD=X", True),
        ("NZDSGD", "NZDSGD=X", True),
        ("USDSGD", "USDSGD=X", True),
        ("CADSGD", "CADSGD=X", True),
    ],
    "HKD": [
        ("USDHKD", "USDHKD=X", True),
        ("EURHKD", "EURHKD=X", True),
        ("GBPHKD", "GBPHKD=X", True),
        ("AUDHKD", "AUDHKD=X", True),
    ],
    "CNY": [
        ("USDCNY", "CNY=X", True),
    ],
}


# ---------------------------------------------------------
# CORE LOGIC: SCORING FUNCTION
# ---------------------------------------------------------
def _compute_single_score(p_open, p_high, p_low, p_close, c_close, trend_mode_val, reversed_flag):
  green_candle = p_close >= p_open
  if green_candle:
    midline = ((p_close - p_open) / 2.0) + p_open
  else:
    midline = ((p_open - p_close) / 2.0) + p_close

  score = 0

  if trend_mode_val == "Open, High, Low, Close + Midline":
    if green_candle:
      if c_close >= midline and c_close < p_close:
        score = -1 if reversed_flag else 1
      elif c_close < midline and c_close > p_open:
        score = 1 if reversed_flag else -1
      elif c_close >= p_close and c_close < p_high:
        score = -2 if reversed_flag else 2
      elif c_close <= p_open and c_close > p_low:
        score = 2 if reversed_flag else -2
      elif c_close >= p_high:
        score = -3 if reversed_flag else 3
      elif c_close <= p_low:
        score = 3 if reversed_flag else -3
    else:  # Red candle
      if c_close >= midline and c_close < p_open:
        score = -1 if reversed_flag else 1
      elif c_close < midline and c_close > p_close:
        score = 1 if reversed_flag else -1
      elif c_close >= p_open and c_close < p_high:
        score = -2 if reversed_flag else 2
      elif c_close <= p_close and c_close > p_low:
        score = 2 if reversed_flag else -2
      elif c_close >= p_high:
        score = -3 if reversed_flag else 3
      elif c_close <= p_low:
        score = 3 if reversed_flag else -3

  elif trend_mode_val == "Above/Below Midline":
    if c_close >= midline:
      score = -3 if reversed_flag else 3
    else:
      score = 3 if reversed_flag else -3

  return score


def calculate_score(df, trend_mode_val, reversed_flag):
  if df is None or len(df) < 2:
    return "0", 0

  # Current score uses iloc[-2] as previous and iloc[-1] as current
  curr_score = _compute_single_score(
      df["Open"].iloc[-2], df["High"].iloc[-2], df["Low"].iloc[-2], df["Close"].iloc[-2],
      df["Close"].iloc[-1], trend_mode_val, reversed_flag
  )

  # Past score uses iloc[-3] as previous and iloc[-2] as current (if available)
  if len(df) >= 3:
    past_score = _compute_single_score(
        df["Open"].iloc[-3], df["High"].iloc[-3], df["Low"].iloc[-3], df["Close"].iloc[-3],
        df["Close"].iloc[-2], trend_mode_val, reversed_flag
    )
    display_val = f"{past_score}{curr_score}"
  else:
    display_val = str(curr_score)

  return display_val, curr_score


@st.cache_data(ttl=60)
def fetch_data(ticker, timeframe):
  try:
    if timeframe == "60m":
      period = "60d"
      interval = "60m"
    elif timeframe == "1d":
      period = "6mo"
      interval = "1d"
    elif timeframe == "1wk":
      period = "2y"
      interval = "1wk"
    elif timeframe == "1mo":
      period = "5y"
      interval = "1mo"
    elif timeframe == "3mo":
      period = "max"
      interval = "3mo"
    elif timeframe == "1y":
      period = "max"
      interval = "1mo"
    else:
      period = "60d"
      interval = "1d"

    data = yf.download(ticker, period=period, interval=interval, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
      data.columns = data.columns.get_level_values(0)
    return data
  except Exception as e:
    return None


# ---------------------------------------------------------
# ROW-WISE STYLING FUNCTION
# ---------------------------------------------------------
def style_row(row):
  styles = [""] * len(row)

  for i, col in enumerate(row.index):
    val = row[col]
    if col not in ["Ticker", "Reverse"]:
      if pd.notna(val):
        val_str = str(val)
        matches = re.findall(r'-?[0-3]', val_str)
        
        if matches:
          scores = [int(m) for m in matches]
          curr_val = scores[-1]
          past_val = scores[0] if len(scores) > 1 else None

          # Check if either the current OR past score meets the extreme threshold (>= 3 or <= -3)
          is_extreme = (curr_val >= 3 or curr_val <= -3) or (
              past_val is not None and (past_val >= 3 or past_val <= -3)
          )

          if is_extreme:
            # Determine whether to use bullish or bearish extreme styling based on the extreme score
            target_val = (
                curr_val
                if (curr_val >= 3 or curr_val <= -3)
                else past_val
            )
            if target_val >= 3:
              styles[i] = (
                  "background-color: ​#00E676; color: #00bfff; font-weight:"
                  " bold;"
              )
            else:
              styles[i] = (
                  "background-color: #b30000; color: #00bfff; font-weight:"
                  " bold;"
              )
          else:
            # Standard styling for non-extreme scores based on the current value
            if curr_val == 2:
              styles[i] = (
                  "background-color: #008143; color: black; font-weight: bold;"
              )
            elif curr_val == 1:
              styles[i] = "background-color: #004624; color: black;"
            elif curr_val == -2:
              styles[i] = (
                  "background-color: #aa0000; color: black; font-weight: bold;"
              )
            elif curr_val == -1:
              styles[i] = "background-color: #690000; color: black;"
            else:
              styles[i] = "background-color: #808080; color: #00bfff;"
        else:
          styles[i] = "background-color: #808080; color: #00bfff;"

  return styles


def get_group_df(tickers_to_scan):
  results = []
  for display_name, yf_ticker, rev_flag in tickers_to_scan:
    res1 = calculate_score(fetch_data(yf_ticker, tf1), trend_mode, rev_flag) if tf1_on else ("0", 0)
    res2 = calculate_score(fetch_data(yf_ticker, tf2), trend_mode, rev_flag) if tf2_on else ("0", 0)
    res3 = calculate_score(fetch_data(yf_ticker, tf3), trend_mode, rev_flag) if tf3_on else ("0", 0)
    res4 = calculate_score(fetch_data(yf_ticker, tf4), trend_mode, rev_flag) if tf4_on else ("0", 0)

    s1_str, _ = res1
    s2_str, _ = res2
    s3_str, _ = res3
    s4_str, _ = res4

    results.append({
        "Ticker": display_name,
        "Reverse": "Yes" if rev_flag else "No",
        f"TF 1 ({tf1})": s1_str,
        f"TF 2 ({tf2})": s2_str,
        f"TF 3 ({tf3})": s3_str,
        f"TF 4 ({tf4})": s4_str,
    })
  return pd.DataFrame(results)


# ---------------------------------------------------------
# AUTO-UPDATING DASHBOARD FRAGMENT
# ---------------------------------------------------------

def render_scanner_dashboard():
  @st.fragment(run_every=run_interval)
  def dashboard_fragment():
    st.caption(
        f"⏱️ Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    group_items = list(group_tickers.items())

    for i in range(0, len(group_items), 2):
      cols = st.columns(2)

      with cols[0]:
        group_name_1, tickers_1 = group_items[i]
        st.markdown(f"##### 💱 {group_name_1}")
        df_1 = get_group_df(tickers_1)
        if not df_1.empty:
          st.table(df_1.style.apply(style_row, axis=1))
        else:
          st.info(f"No tickers for {group_name_1}")

      if i + 1 < len(group_items):
        with cols[1]:
          group_name_2, tickers_2 = group_items[i + 1]
          st.markdown(f"##### 💱 {group_name_2}")
          df_2 = get_group_df(tickers_2)
          if not df_2.empty:
            st.table(df_2.style.apply(style_row, axis=1))
          else:
            st.info(f"No tickers for {group_name_2}")

      st.markdown("---")

  dashboard_fragment()


render_scanner_dashboard()
