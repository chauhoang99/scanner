from datetime import datetime, timedelta
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

st.title("📈 Scanner Dashboard (Dual Mobile Layout)")

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

st.sidebar.subheader("Timeframes to Scan")
tf1_on = st.sidebar.checkbox("Timeframe #1 On/Off", value=True)
tf1 = st.sidebar.selectbox("Timeframe #1", ["60m", "1d", "1wk"], index=0)

tf2_on = st.sidebar.checkbox("Timeframe #2 On/Off", value=True)
tf2 = st.sidebar.selectbox(
    "Timeframe #2", ["60m", "1d", "1wk", "1mo"], index=1
)

tf3_on = st.sidebar.checkbox("Timeframe #3 On/Off", value=True)
tf3 = st.sidebar.selectbox(
    "Timeframe #3", ["60m", "1d", "1wk", "1mo"], index=2
)

tf4_on = st.sidebar.checkbox("Timeframe #4 On/Off", value=True)
tf4 = st.sidebar.selectbox(
    "Timeframe #4", ["60m", "1d", "1wk", "1mo"], index=3
)

total_score_on = st.sidebar.checkbox("Total Combined Score On/Off", value=True)

# Define Tickers per group (matching OANDA FX pairs from Pine Script)
group_tickers = {
    "USD": [
        ("OANDA:EURUSD", "EURUSD=X", True),
        ("OANDA:GBPUSD", "GBPUSD=X", True),
        ("OANDA:AUDUSD", "AUDUSD=X", True),
        ("OANDA:NZDUSD", "NZDUSD=X", True),
        ("OANDA:USDCAD", "USDCAD=X", False),
        ("OANDA:USDCHF", "USDCHF=X", False),
        ("OANDA:USDJPY", "USDJPY=X", False),
        ("OANDA:USDSGD", "USDSGD=X", False),
    ],
    "EUR": [
        ("OANDA:EURUSD", "EURUSD=X", False),
        ("OANDA:EURGBP", "EURGBP=X", False),
        ("OANDA:EURAUD", "EURAUD=X", False),
        ("OANDA:EURNZD", "EURNZD=X", False),
        ("OANDA:EURCAD", "EURCAD=X", False),
        ("OANDA:EURCHF", "EURCHF=X", False),
        ("OANDA:EURJPY", "EURJPY=X", False),
        ("OANDA:EURSGD", "EURSGD=X", False),
    ],
    "GBP": [
        ("OANDA:GBPUSD", "GBPUSD=X", False),
        ("OANDA:EURGBP", "EURGBP=X", True),
        ("OANDA:GBPAUD", "GBPAUD=X", False),
        ("OANDA:GBPNZD", "GBPNZD=X", False),
        ("OANDA:GBPCAD", "GBPCAD=X", False),
        ("OANDA:GBPCHF", "GBPCHF=X", False),
        ("OANDA:GBPJPY", "GBPJPY=X", False),
        ("OANDA:GBPSGD", "GBPSGD=X", False),
    ],
    "AUD": [
        ("OANDA:AUDUSD", "AUDUSD=X", False),
        ("OANDA:EURAUD", "EURAUD=X", True),
        ("OANDA:GBPAUD", "GBPAUD=X", True),
        ("OANDA:AUDNZD", "AUDNZD=X", False),
        ("OANDA:AUDCAD", "AUDCAD=X", False),
        ("OANDA:AUDCHF", "AUDCHF=X", False),
        ("OANDA:AUDJPY", "AUDJPY=X", False),
        ("OANDA:AUDSGD", "AUDSGD=X", False),
    ],
    "CAD": [
        ("OANDA:EURCAD", "EURCAD=X", True),
        ("OANDA:GBPCAD", "GBPCAD=X", True),
        ("OANDA:AUDCAD", "AUDCAD=X", True),
        ("OANDA:USDCAD", "USDCAD=X", True),
        ("OANDA:CADCHF", "CADCHF=X", False),
        ("OANDA:CADJPY", "CADJPY=X", False),
    ],
    "NZD": [
        ("OANDA:NZDUSD", "NZDUSD=X", False),
        ("OANDA:EURNZD", "EURNZD=X", True),
        ("OANDA:GBPNZD", "GBPNZD=X", True),
        ("OANDA:AUDNZD", "AUDNZD=X", True),
        ("OANDA:NZDCAD", "NZDCAD=X", False),
        ("OANDA:NZDCHF", "NZDCHF=X", False),
    ],
    "JPY": [
        ("OANDA:EURJPY", "EURJPY=X", True),
        ("OANDA:GBPJPY", "GBPJPY=X", True),
        ("OANDA:AUDJPY", "AUDJPY=X", True),
        ("OANDA:NZDJPY", "NZDJPY=X", True),
        ("OANDA:USDJPY", "USDJPY=X", True),
        ("OANDA:CADJPY", "CADJPY=X", True),
    ],
    "CHF": [
        ("OANDA:EURCHF", "EURCHF=X", True),
        ("OANDA:GBPCHF", "GBPCHF=X", True),
        ("OANDA:AUDCHF", "AUDCHF=X", True),
        ("OANDA:NZDCHF", "NZDCHF=X", True),
        ("OANDA:USDCHF", "USDCHF=X", True),
        ("OANDA:CADCHF", "CADCHF=X", True),
    ],
    "SGD": [
        ("OANDA:EURSGD", "EURSGD=X", True),
        ("OANDA:GBPSGD", "GBPSGD=X", True),
        ("OANDA:AUDSGD", "AUDSGD=X", True),
        ("OANDA:NZDSGD", "NZDSGD=X", True),
        ("OANDA:USDSGD", "USDSGD=X", True),
        ("OANDA:CADSGD", "CADSGD=X", True),
    ],
    "HKD": [
        ("OANDA:USDHKD", "USDHKD=X", True),
        ("OANDA:EURHKD", "EURHKD=X", True),
        ("OANDA:GBPHKD", "GBPHKD=X", True),
        ("OANDA:AUDHKD", "AUDHKD=X", True),
    ],
    "CNY": [
        ("OANDA:USDCNH", "USDCNH=X", True),
    ],
}


# ---------------------------------------------------------
# CORE LOGIC: SCORING FUNCTION
# ---------------------------------------------------------
def calculate_score(df, trend_mode_val, reversed_flag):
  if df is None or len(df) < 2:
    return 0

  prev_open = df["Open"].iloc[-2]
  prev_high = df["High"].iloc[-2]
  prev_low = df["Low"].iloc[-2]
  prev_close = df["Close"].iloc[-2]
  curr_close = df["Close"].iloc[-1]

  green_candle = prev_close >= prev_open
  if green_candle:
    midline = ((prev_close - prev_open) / 2.0) + prev_open
  else:
    midline = ((prev_open - prev_close) / 2.0) + prev_close

  score = 0

  if trend_mode_val == "Open, High, Low, Close + Midline":
    if green_candle:
      if curr_close >= midline and curr_close < prev_close:
        score = -1 if reversed_flag else 1
      elif curr_close < midline and curr_close > prev_open:
        score = 1 if reversed_flag else -1
      elif curr_close >= prev_close and curr_close < prev_high:
        score = -2 if reversed_flag else 2
      elif curr_close <= prev_open and curr_close > prev_low:
        score = 2 if reversed_flag else -2
      elif curr_close >= prev_high:
        score = -3 if reversed_flag else 3
      elif curr_close <= prev_low:
        score = 3 if reversed_flag else -3
    else:  # Red candle
      if curr_close >= midline and curr_close < prev_open:
        score = -1 if reversed_flag else 1
      elif curr_close < midline and curr_close > prev_close:
        score = 1 if reversed_flag else -1
      elif curr_close >= prev_open and curr_close < prev_high:
        score = -2 if reversed_flag else 2
      elif curr_close <= prev_close and curr_close > prev_low:
        score = 2 if reversed_flag else -2
      elif curr_close >= prev_high:
        score = -3 if reversed_flag else 3
      elif curr_close <= prev_low:
        score = 3 if reversed_flag else -3

  elif trend_mode_val == "Above/Below Midline":
    if curr_close >= midline:
      score = -3 if reversed_flag else 3
    else:
      score = 3 if reversed_flag else -3

  return score


@st.cache_data(ttl=300)
def fetch_data(ticker, interval):
  try:
    period = "60d"
    if interval == "1wk":
      period = "1y"
    elif interval == "1mo":
      period = "2y"
    data = yf.download(ticker, period=period, interval=interval, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
      data.columns = data.columns.get_level_values(0)
    return data
  except Exception as e:
    return None


# ---------------------------------------------------------
# ROW-WISE STYLING FUNCTION (Strict Total Score Condition)
# ---------------------------------------------------------
def style_row(row):
  styles = [""] * len(row)
  tf_values = []

  for i, col in enumerate(row.index):
    val = row[col]
    if col not in ["Ticker", "Reverse", "Total Score"]:
      if isinstance(val, (int, float)):
        tf_values.append(val)
        if val >= 3:
          styles[i] = "background-color: #00ff84; color: black; font-weight: bold;"
        elif val == 2:
          styles[i] = "background-color: #008143; color: white; font-weight: bold;"
        elif val == 1:
          styles[i] = "background-color: #004624; color: white;"
        elif val <= -3:
          styles[i] = "background-color: #ff0000; color: white; font-weight: bold;"
        elif val == -2:
          styles[i] = "background-color: #aa0000; color: white; font-weight: bold;"
        elif val == -1:
          styles[i] = "background-color: #690000; color: white;"
        else:
          styles[i] = "background-color: #808080; color: white;"

    elif col == "Total Score":
      if tf_values:
        all_positive = all(v > 0 for v in tf_values)
        all_negative = all(v < 0 for v in tf_values)

        if all_positive:
          styles[i] = (
              "background-color: #00ff84; color: black; font-weight: bold;"
          )
        elif all_negative:
          styles[i] = (
              "background-color: #ff0000; color: white; font-weight: bold;"
          )
        else:
          styles[i] = ""

  return styles


def get_group_df(tickers_to_scan):
  results = []
  for display_name, yf_ticker, rev_flag in tickers_to_scan:
    s1 = (
        calculate_score(fetch_data(yf_ticker, tf1), trend_mode, rev_flag)
        if tf1_on
        else 0
    )
    s2 = (
        calculate_score(fetch_data(yf_ticker, tf2), trend_mode, rev_flag)
        if tf2_on
        else 0
    )
    s3 = (
        calculate_score(fetch_data(yf_ticker, tf3), trend_mode, rev_flag)
        if tf3_on
        else 0
    )
    s4 = (
        calculate_score(fetch_data(yf_ticker, tf4), trend_mode, rev_flag)
        if tf4_on
        else 0
    )

    total = s1 + s2 + s3 + s4 if total_score_on else 0

    results.append({
        "Ticker": display_name,
        "Reverse": "Yes" if rev_flag else "No",
        f"TF 1 ({tf1})": s1,
        f"TF 2 ({tf2})": s2,
        f"TF 3 ({tf3})": s3,
        f"TF 4 ({tf4})": s4,
        "Total Score": total if total_score_on else "N/A",
    })
  return pd.DataFrame(results)


# ---------------------------------------------------------
# ITERATE & DISPLAY 2 TABLES PER ROW (FORCED SIDE-BY-SIDE)
# ---------------------------------------------------------
st.markdown(f"### Active Mode: `{trend_mode}`")

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

# Summary Notes
st.markdown("""
### 💡 Dashboard Guide:
* **Forced Mobile Dual Columns**: Custom CSS forces two tables to sit side-by-side even on narrow mobile displays instead of collapsing into a single column.
* **Reverse Column**: Shows whether scoring is reversed (`Yes`) or normal (`No`).
* **Total Score Highlight Rule**: The **Total Score** column highlights only if **all active timeframes** are strictly positive (`> 0`) or negative (`< 0`).
""")