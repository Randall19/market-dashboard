"""
Created on May 21, 2026
@author: randall
"""
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streamlit Dashboard for Market Data
@author: randall
"""
import yfinance as yf
import pandas as pd
import requests
import datetime
import streamlit as st
import json # Import json for potential debugging, though Altair handles most of it
import time
import numpy as np 
import os
import json, logging
logger = logging.getLogger(__name__)


# At the top of the file (after imports)
from streamlit import cache_data

# Configure the page before calling any other Streamlit commands.
st.set_page_config(page_title="Market Dashboard", layout="wide")




# Improved sanitizer by Claude
def altair_sanitise(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """
    Replace numpy NaN *and* Python None with a JSON‑serialisable None.
    Also makes sure the `date` column is a plain ``datetime.date``.
    """
    df = df.copy()
    for col in columns:
        if col in df.columns:
            # Convert Python None → np.nan (so .replace works uniformly)
            df[col] = df[col].where(df[col].notna(), np.nan)
            df[col] = df[col].replace({np.nan: None})
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def _debug_aave_response(resp: requests.Response) -> None:
    """
    Log the raw payload when the response is not the shape we expect.
    This function is called **only** when something looks wrong,
    so you don’t flood the console during normal operation.
    """
    try:
        # Try to decode JSON *just* for logging – we may already know it’s broken.
        payload = resp.json()
    except Exception:
        logger.error("Aave response is not valid JSON: %s", resp.text[:200])
        return

    # If we got JSON but it wasn’t a dict with a "data" key → warning.
    if not isinstance(payload, dict) or "data" not in payload:
        logger.warning(
            "Unexpected Aave JSON structure (type=%s): %s",
            type(payload),
            json.dumps(payload, indent=2)[:500],
        )

# Retrieve FRED API key securely.
# Streamlit Community Cloud: configure FRED_API_KEY in App settings > Secrets.
# Linux/local use: keep using the FRED_API_KEY environment variable.
try:
    FRED_API_KEY = st.secrets["FRED_API_KEY"]
except Exception:
    FRED_API_KEY = os.getenv("FRED_API_KEY")

if not FRED_API_KEY:
    raise ValueError(
        "FRED_API_KEY is not configured. Set it in Streamlit Cloud Secrets "
        "or as a local environment variable."
    )



TODAY = datetime.date.today()
END_DATE = TODAY - datetime.timedelta(days=1)
START_DATE = END_DATE - datetime.timedelta(days=360)

SERIES = {
    "SOFR": "SOFR",
    "FFR": "DFF",
    "DGS10": "DGS10",
    "USD Index (Proxy)": "DTWEXBGS",
    "USD Index (Inflation Adj)": "RTWEXBGS",
    
    # Credit Market Stress
    "HY OAS (%)": "BAMLH0A0HYM2"
}   
    

# ------------------------
# Functions
# ------------------------
#@st.cache_data(ttl=3600)
# Define GET FRED FUNCTION HERE**************************
def get_fred_series(series_id: str) -> pd.DataFrame:
    """Fetch a FRED series and report the actual response if it fails."""

    url = "https://api.stlouisfed.org/fred/series/observations"

    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": START_DATE.strftime("%Y-%m-%d"),
        "observation_end": END_DATE.strftime("%Y-%m-%d")
    }

    try:
        response = requests.get(url, params=params, timeout=30)

        print(f"\nFRED {series_id}")
        print(f"HTTP status: {response.status_code}")

        if response.status_code != 200:
            print("FRED response:")
            print(response.text[:1000])

            dates = pd.date_range(
                START_DATE,
                END_DATE,
                freq="B"
            ).date

            return pd.DataFrame({
                "date": dates,
                series_id: [None] * len(dates)
            })

        data = response.json()

        df = pd.DataFrame(data["observations"])

        df["date"] = pd.to_datetime(
            df["date"]
        ).dt.date

        df[series_id] = pd.to_numeric(
            df["value"],
            errors="coerce"
        )

        print(
            f"{series_id}: {len(df)} observations received"
        )

        return df[["date", series_id]]

    except Exception as e:

        print(
            f"ERROR retrieving FRED {series_id}: {type(e).__name__}: {e}"
        )

        dates = pd.date_range(
            START_DATE,
            END_DATE,
            freq="B"
        ).date

        return pd.DataFrame({
            "date": dates,
            series_id: [None] * len(dates)
        })
# DEFINE GET STABLECOIN FUNCTION HERE*****************************
def get_stablecoin_marketcap():

    url = "https://stablecoins.llama.fi/stablecoincharts/all"

    try:
        response = requests.get(
            url,
            timeout=30
        )

        print("\nSTABLECOIN API")
        print("HTTP status:", response.status_code)

        if response.status_code != 200:
            print(response.text[:1000])
            return pd.DataFrame(
                columns=["date", "Stablecoin Mkt Cap"]
            )

        data = response.json()

        print(
            "Number of records returned:",
            len(data)
        )

        if len(data) > 0:
            print(
                "First record:",
                data[0]
            )

        records = []

        for entry in data:

            date = datetime.datetime.fromtimestamp(
                int(entry["date"])
            ).date()

            total_circulating = entry.get(
                "totalCirculatingUSD",
                {}
            )

            total_usd = sum(
                total_circulating.values()
            )

            records.append({
                "date": date,
                "Stablecoin Mkt Cap": total_usd
            })

        df = pd.DataFrame(records)

        df = df[
            (df["date"] >= START_DATE) &
            (df["date"] <= END_DATE)
        ]

        df["date"] = pd.to_datetime(df["date"])

        df.set_index("date", inplace=True)

        df = df.resample("B").last()

        df.reset_index(inplace=True)

        df["date"] = df["date"].dt.date

        print(
            "Stablecoin rows after filtering:",
            len(df)
        )

        return df

    except Exception as e:

        print(
            "STABLECOIN ERROR:",
            type(e).__name__,
            e
        )

        return pd.DataFrame(
            columns=["date", "Stablecoin Mkt Cap"]
        )
  

# ------------------------
# AAVE USDC SUPPLY APY
# ------------------------
#------------------------------------------------------------------------
# ----------------------------------------------------------------------
# AAVE USDC SUPPLY APY
# ----------------------------------------------------------------------
# AAVE USDC SUPPLY APY – DAILY values for the last six months




#----------------
#---------------
#------------------
# --------------------------------------------
# Claude Second Time Modified get_aave_supply_apy Function
# AAVE USDC SUPPLY APY – DAILY values
# AAVE USDC SUPPLY APY – DAILY values
@st.cache_data(ttl=3600)
def get_aave_supply_apy(window: str = "LAST_SIX_MONTHS") -> pd.DataFrame:
    """
    Pull USDC-Supply-APY from Aave's GraphQL endpoint.
    """
    url = "https://api.v3.aave.com/graphql"

    query = """
    query SupplyAPYHistory($request: SupplyAPYHistoryRequest!) {
      value: supplyAPYHistory(request: $request) {
        avgRate { value }
        date
      }
    }
    """

    payload = {
        "operationName": "SupplyAPYHistory",
        "query": query,
        "variables": {
            "request": {
                "chainId": 1,
                "market": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
                "underlyingToken": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "window": window,
            }
        },
    }

    # Retry loop
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=30)
        except requests.RequestException as exc:
            logger.exception("Aave request network error (attempt %s)", attempt + 1)
            if attempt == 2:
                return pd.DataFrame(columns=["date", "USDC Supply APY"])
            time.sleep(5)
            continue

        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 30))
            logger.info("Aave 429 – waiting %s s (attempt %s)", wait, attempt + 1)
            time.sleep(wait)
            continue

        if resp.status_code != 200:
            logger.error("Aave returned status %s: %s", resp.status_code, resp.text[:200])
            return pd.DataFrame(columns=["date", "USDC Supply APY"])

        break
    else:
        logger.warning("Aave API kept failing after retries.")
        return pd.DataFrame(columns=["date", "USDC Supply APY"])

    # Parse JSON response
    try:
        data = resp.json()
    except json.JSONDecodeError:
        logger.error("Aave returned malformed JSON: %s", resp.text[:200])
        return pd.DataFrame(columns=["date", "USDC Supply APY"])

    if not isinstance(data, dict):
        logger.error("Aave response is not a dict: %s", type(data))
        return pd.DataFrame(columns=["date", "USDC Supply APY"])

    # Extract values - handle both nested and direct structures
    raw_vals = None
    if "data" in data and isinstance(data["data"], dict):
        raw_vals = data["data"].get("value")
    elif "value" in data:
        raw_vals = data["value"]

    # Empty-window handling
    if not raw_vals:
        logger.warning("Aave returned no data for window='%s'", window)
        larger = {
            "LAST_DAY": "LAST_WEEK",
            "LAST_WEEK": "LAST_MONTH",
            "LAST_MONTH": "LAST_SIX_MONTHS",
            "LAST_SIX_MONTHS": "LAST_YEAR",
        }.get(window)
        if larger:
            return get_aave_supply_apy(window=larger)
        return pd.DataFrame(columns=["date", "USDC Supply APY"])

    # Build DataFrame
    rows = []
    for item in raw_vals:
        dt_raw = item.get("date")
        rate_obj = item.get("avgRate", {})
        rate_raw = rate_obj.get("value") if isinstance(rate_obj, dict) else None
        
        if dt_raw is None or rate_raw is None:
            continue
        
        try:
            rows.append({
                "datetime": pd.to_datetime(dt_raw),
                "USDC Supply APY": float(rate_raw) * 100,
            })
        except (ValueError, TypeError) as e:
            logger.warning("Skipping malformed row: %s", e)
            continue

    if not rows:
        return pd.DataFrame(columns=["date", "USDC Supply APY"])

    raw_df = pd.DataFrame(rows)

    # Down-sample to daily - keep the last observation of each day
    daily_df = (
        raw_df.set_index("datetime")
        .resample("D")
        .last()
        .dropna()
        .reset_index()
    )
    daily_df["date"] = daily_df["datetime"].dt.date
    
    return daily_df[["date", "USDC Supply APY"]]


# Cached wrapper
def get_aave_supply_apy_cached(window: str = "LAST_SIX_MONTHS") -> pd.DataFrame:
    """Thin wrapper that forwards to the cached function."""
    return get_aave_supply_apy(window=window)

# -------------------------------------------------
# Cached-wrapper
# -------------------------------------------------
def get_aave_supply_apy_cached(window: str = "LAST_SIX_MONTHS") -> pd.DataFrame:
    """Thin wrapper that forwards to the cached function."""
    return get_aave_supply_apy(window=window)


#--------------------------------------------------
#------------------------------------------------
# ------------------------------------------------------------------
# -------------------------------------------------
# Cached‑wrapper – a tiny indirection that keeps the
# @st.cache_data decorator from being re‑applied on
# every file reload.
# -------------------------------------------------
def get_aave_supply_apy_cached(window: str = "LAST_SIX_MONTHS") -> pd.DataFrame:
    """Thin wrapper that forwards to the cached function."""
    return get_aave_supply_apy(window=window)



# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# Fetch the Aave series (daily) and print a short debug summary
# ----------------------------------------------------------------------
aave_supply_df = get_aave_supply_apy_cached()        # uses the six month  window internally
print("\n====================")
print("AAVE SUPPLY DATA (daily)")
print("====================")
print(aave_supply_df.head())
print("Rows →", aave_supply_df.shape[0])

# -------------------------------------------------
#  If we got any rows, make sure the date column is a plain Python date
#  and collapse duplicate dates (Aave sometimes returns several rows for the same day)
# -------------------------------------------------
if not aave_supply_df.empty:
    aave_supply_df["date"] = pd.to_datetime(aave_supply_df["date"]).dt.date
    # Keep the last observed APY for each day (you could also use .mean())
    aave_supply_df = aave_supply_df.groupby("date", as_index=False).last()
else:
    st.info("ℹ️ No Aave USDC‑Supply‑APY data returned for the selected window.")




# -------------------------------------------------

# -------------------------------------------------








      

# ------------------------
# Fetch SPY and VIX and other market Data
# ------------------------
spy = yf.download("SPY", start=START_DATE, end=END_DATE, progress=False)
vix = yf.download("^VIX", start=START_DATE, end=END_DATE, progress=False)
# DIAGNOSE VIX YF*****************************
print("\n========== VIX DEBUG ==========")
print("VIX empty:", vix.empty)
print("VIX shape:", vix.shape)
print("VIX columns:", vix.columns)
print(vix.tail())
print("================================")
shel = yf.download("SHEL", start=START_DATE, end=END_DATE, progress=False)
gld  = yf.download("GLD",  start=START_DATE, end=END_DATE, progress=False)
vtip = yf.download("VTIP", start=START_DATE, end=END_DATE, progress=False)
tlt  = yf.download("TLT",  start=START_DATE, end=END_DATE, progress=False)

crcl = yf.download("CRCL", start=START_DATE, end=END_DATE, progress=False)
dram = yf.download("DRAM", start=START_DATE, end=END_DATE, progress=False)
jnk  = yf.download("JNK",  start=START_DATE, end=END_DATE, progress=False)
emb  = yf.download("EMB",  start=START_DATE, end=END_DATE, progress=False)

# Added: Yahoo Finance USD/JPY data (Japanese Yen against the US dollar)
jpy_usd = yf.download("JPY=X", start=START_DATE, end=END_DATE, progress=False)
# Normalize to the same date format as master_df (Python date) for clean merges
jpy_usd = jpy_usd.reset_index()[["Date", "Close"]]
jpy_usd.columns = ["date", "JPYUSD"]
jpy_usd["date"] = pd.to_datetime(jpy_usd["date"]).dt.date # Ensure datetime.date objects


# Reset index and standardize for all yfinance downloads
# This ensures consistency in the 'date' column type across all separately downloaded DataFrames.
# The get_fred_series and get_stablecoin_marketcap functions already return datetime.date objects.
# Improved by Clause to guard against return of empty DataFrame

def standardize_yf_df(df, column_name):
    if df.empty:
        # Return an empty frame with the correct columns so the merge still works
        return pd.DataFrame({ "date": [], column_name: [] })
    df = df.reset_index()[["Date", "Close"]]
    df.columns = ["date", column_name]
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df





spy = standardize_yf_df(spy, "SPY")
vix = standardize_yf_df(vix, "VIX")
shel = standardize_yf_df(shel, "SHEL")
gld = standardize_yf_df(gld, "GLD")
vtip = standardize_yf_df(vtip, "VTIP")
tlt = standardize_yf_df(tlt, "TLT")
crcl = standardize_yf_df(crcl, "CRCL")
dram = standardize_yf_df(dram, "DRAM") # Apply to DRAM too
jnk = standardize_yf_df(jnk, "JNK")
emb = standardize_yf_df(emb, "EMB")


# ------------------------
# Build Master DataFrame
# ------------------------
date_range = pd.bdate_range(start=START_DATE, end=END_DATE)
master_df = pd.DataFrame({"date": date_range.date}) # Create with datetime.date objects

# Merge FRED data
for name, series_id in SERIES.items():
    df = get_fred_series(series_id)
    master_df = master_df.merge(df, on="date", how="left")

# Merge Yahoo JPY data (JPY=X)
master_df = master_df.merge(jpy_usd, on="date", how="left")

# Merge stablecoin data
stable_df = get_stablecoin_marketcap()
master_df = master_df.merge(stable_df, on="date", how="left")

# ------------------------
# AAVE SUPPLY APY
# ------------------------


    










# --- Crucial: Merge other stock data, calculate spreads, and then merge USD index ---

# Now that master_df is built with FRED and stablecoins, we can merge other dataframes.
# Note: This approach assumes you want SPY, VIX, etc., to be separate dataframes plotted directly,
# and only want the USD index to be integrated into master_df for potential future use
# or if you wish to plot it alongside other integrated metrics.
# If you want SPY, VIX, etc., also in master_df, you'd merge them here.

# Calculate SOFR spread BEFORE merging USD index, as it uses FRED data
# DFF is merged in first by the loop above, so it's available.
if "SOFR" in master_df.columns and "DFF" in master_df.columns:
    master_df["SOFR_Spread"] = master_df["SOFR"] - master_df["DFF"]
    master_df.rename(columns={"DFF": "FFR"}, inplace=True)
else:
    print("Warning: SOFR or DFF not found in master_df. SOFR_Spread calculation skipped.")


# The FRED data for USD Indices are now directly merged into master_df in the loop above.
# We don't need a separate merge step for them anymore.

# FINAL MERGE: Merge all standardized yfinance data into master_df
# This ensures all data uses the 'date' column with datetime.date objects.
master_df = master_df.merge(spy, on="date", how="left")
master_df = master_df.merge(vix, on="date", how="left")
master_df = master_df.merge(shel, on="date", how="left")
master_df = master_df.merge(gld, on="date", how="left")
master_df = master_df.merge(vtip, on="date", how="left")
master_df = master_df.merge(tlt, on="date", how="left")
master_df = master_df.merge(crcl, on="date", how="left") # Merged after processing
master_df = master_df.merge(dram, on="date", how="left") # Merged after processing
master_df = master_df.merge(jnk, on="date", how="left")
master_df = master_df.merge(emb, on="date", how="left")


# Handle missing data AFTER all merges
master_df = master_df.sort_values("date")
master_df.ffill(inplace=True)
# Merge the Aave USDC Supply-APY column into master_df
# -------------------------------------------------
#  Merge the Aave USDC‑Supply‑APY column into master_df
# -------------------------------------------------
#  Merge the Aave USDC‑Supply‑APY column into master_df
# -------------------------------------------------
if not aave_supply_df.empty:
    # aave_supply_df already has a plain Python `date` column from the function above
    master_df = master_df.merge(
        aave_supply_df,
        on="date",
        how="left",          # keep every master row; missing APY becomes NaN (later filled)
    )
else:
    st.info("ℹ️ No Aave USDC‑Supply‑APY data returned for the selected window.")
#-----------------------------------
#  Replace any remaining np.nan with JSON‑friendly None
# -------------------------------------------------
altair_cols = [
    "DGS10",
    "DTWEXBGS",
    "RTWEXBGS",
    "SOFR",
    "FFR",
    "Stablecoin Mkt Cap",
    "JPYUSD",
    "HY OAS (%)"      
]
master_df = altair_sanitise(master_df, altair_cols)


# create the chart_df for display purposes, keep the master_df for calculation purposes
# Move CTRS TO THIS POSITION*******************************
# Chart Time Range Selector
# -------------------------------------------------

CHART_DAYS = st.selectbox(
    "Chart Time Range",
    options=[5, 10, 30, 60, 90, 360],
    index=2,
    format_func=lambda x: f"{x} days"
)

# Calculate the beginning of the selected chart period
chart_start_date = END_DATE - datetime.timedelta(days=CHART_DAYS)

st.caption(
    f"Charts showing {CHART_DAYS} days: "
    f"{chart_start_date} to {END_DATE}"
)

# Consistent month label beneath every chart. The exact daily dates remain
# available in each chart's interactive tooltip.
def show_chart_month_caption():
    start_month = pd.Timestamp(chart_start_date).strftime("%B %Y")
    end_month = pd.Timestamp(END_DATE).strftime("%B %Y")
    if start_month == end_month:
        st.caption(f"Month shown: {start_month}")
    else:
        st.caption(f"Months shown: {start_month} – {end_month}")

# End of Moved CTRS ************************************************************













# -------------------------------------------------
# Create data used only for chart display
# -------------------------------------------------

chart_df = master_df[
    master_df["date"] >= chart_start_date
].copy()
# create the vix_chart_df
vix_chart_df = vix[
    vix["date"] >= chart_start_date
].copy()


# If an entire series is still all None (e.g. after a 429), give it a tiny placeholder
for col in ["DGS10", "DTWEXBGS", "RTWEXBGS"]:
    if master_df[col].isna().all():
        master_df[col] = master_df[col].fillna(0)

# filter the individual Yahoo inance datasets
# -------------------------------------------------
# create the chart_ticker_df that will be used to dislplay data for restricted date range
# -------------------------------------------------
chart_shel_df = shel[shel["date"] >= chart_start_date].copy()
chart_spy_df  = spy[spy["date"] >= chart_start_date].copy()
chart_gld_df  = gld[gld["date"] >= chart_start_date].copy()
chart_vtip_df = vtip[vtip["date"] >= chart_start_date].copy()
chart_tlt_df  = tlt[tlt["date"] >= chart_start_date].copy()
chart_crcl_df = crcl[crcl["date"] >= chart_start_date].copy()
chart_dram_df = dram[dram["date"] >= chart_start_date].copy()
chart_jnk_df  = jnk[jnk["date"] >= chart_start_date].copy()
chart_emb_df  = emb[emb["date"] >= chart_start_date].copy()

# Filter individual Yahoo Finance datasets
chart_vix = vix[vix["date"] >= chart_start_date].copy()
chart_shel = shel[shel["date"] >= chart_start_date].copy()
chart_spy = spy[spy["date"] >= chart_start_date].copy()
chart_gld = gld[gld["date"] >= chart_start_date].copy()
chart_vtip = vtip[vtip["date"] >= chart_start_date].copy()
chart_tlt = tlt[tlt["date"] >= chart_start_date].copy()
chart_crcl = crcl[crcl["date"] >= chart_start_date].copy()
chart_dram = dram[dram["date"] >= chart_start_date].copy()
chart_jnk = jnk[jnk["date"] >= chart_start_date].copy()
chart_emb = emb[emb["date"] >= chart_start_date].copy()

#Troubleshoot by printing out data
print("\n--- FRED USD Index Data ---")
print("USD Index (Proxy) head():")
print(master_df[['date', 'DTWEXBGS']].head())
print("\nUSD Index (Proxy) tail():")
print(master_df[['date', 'DTWEXBGS']].tail())
print("\nUSD Index (Inflation Adj) head():")
print(master_df[['date', 'RTWEXBGS']].head())
print("\nUSD Index (Inflation Adj) tail():")
print(master_df[['date', 'RTWEXBGS']].tail())

# NEW: Print JPY/USD data merged into master_df
print("\n--- JPY/USD Data (JPYUSD) merged into Master DataFrame ---")
print(master_df[['date', 'JPYUSD']].head())
print(master_df[['date', 'JPYUSD']].tail())

print("\n--- Master DataFrame Snippet with FRED USD Indices ---")
print("Master DataFrame head() with FRED USD Indices (showing date and USD Index columns):")
print(master_df[['date', 'DTWEXBGS', 'RTWEXBGS']].head())
print("\nMaster DataFrame tail() with FRED USD Indices (showing date and USD Index columns):")
print(master_df[['date', 'DTWEXBGS', 'RTWEXBGS']].tail())

# Debugging DRAM specifically
print("\n--- Debugging DRAM DataFrame Post-Processing ---")
print(f"Type of 'date' column in dram DataFrame: {dram['date'].dtype}")
print("First 5 values of dram['date'] column:")
print(dram['date'].head())
print(f"Type of first element in dram['date'] using .iloc[0]: {type(dram['date'].iloc[0])}")
print("--------------------------------------------------")

# Debug ICE B of A chart display
print("\n========== MASTER_DF HIGH YIELD TEST ==========")

print("master_df columns:")
print(master_df.columns.tolist())

print("\nBAML column present:")
print("BAMLH0A0HYM2" in master_df.columns)

print("\nHigh Yield friendly name present:")
print("High Yield Credit Spread" in master_df.columns)

if "BAMLH0A0HYM2" in master_df.columns:
    print("\nBAMLH0A0HYM2 last 10 rows:")
    print(
        master_df[
            ["date", "BAMLH0A0HYM2"]
        ].tail(10)
    )

    print(
        "\nBAML non-null count:",
        master_df["BAMLH0A0HYM2"].notna().sum()
    )

if "High Yield Credit Spread" in master_df.columns:
    print("\nHigh Yield Credit Spread last 10 rows:")
    print(
        master_df[
            ["date", "High Yield Credit Spread"]
        ].tail(10)
    )

    print(
        "\nHigh Yield non-null count:",
        master_df["High Yield Credit Spread"].notna().sum()
    )

print("===============================================\n")

# Rename the FRED series to the name used by the chart
# Rename the FRED series to the name used by the chart
master_df.rename(
    columns={
         "BAMLH0A0HYM2": "HY OAS (%)"
    },
    inplace=True
)












print("--- End Debug Prints ---")


# ------------------------
# Streamlit Dashboard
# ------------------------
st.title("📊 Market Data Dashboard")

st.markdown(f"Data from **{START_DATE}** to **{END_DATE}**")
# add section to create dropdown to allow for range of days between 5 and 360
# -------------------------------------------------

# Show raw data
if st.checkbox("Show raw data"):
    st.dataframe(master_df)

import altair as alt

axis_style = alt.Axis(
    labelColor="black",
    titleColor="black",
    labelFontSize=12,
    titleFontSize=14,
    titleFontWeight="bold",
    gridColor="lightgray"
)
# Line charts
# Separate the DSG10 line chart from the SOFR - FFR chart and expand the y-axis scale
# Make the 10 year treasury chart conditional version with 'no data available warning'
st.subheader("10‑Year Treasury Yield (DGS10)")

if chart_df["DGS10"].notna().any():
    dgs_min = chart_df["DGS10"].min()
    dgs_max = chart_df["DGS10"].max()
    padding = (dgs_max - dgs_min) * 0.1

    chart_dgs10 = alt.Chart(chart_df).mark_line().encode(
        x=alt.X("date:T", axis=axis_style),
        y=alt.Y(
            "DGS10:Q",
            scale=alt.Scale(domain=[dgs_min - padding, dgs_max + padding]),
            axis=axis_style
        ),
        tooltip=["date:T", "DGS10:Q"]
    ).interactive()

    st.altair_chart(chart_dgs10, use_container_width=True)
    show_chart_month_caption()
else:
    st.warning("🚫 No DGS10 data available (FRED rate‑limit).")

# Insert HY OAS as measure of credit stress**********************************************************
##########################################################################
# New HYCS Chart
# -------------------------------------------------
# High Yield Credit Spread
# -------------------------------------------------

st.subheader(
    "High Yield Credit Spread (ICE BofA Option-Adjusted Spread)"
)

if "HY OAS (%)" in master_df.columns:

    hy_df = master_df.loc[
        master_df["date"] >= chart_start_date,
        ["date", "HY OAS (%)"]
    ].dropna()

    if not hy_df.empty:

        chart_hy = alt.Chart(hy_df).mark_line().encode(
            x=alt.X(
                "date:T",
                axis=axis_style
            ),
            y=alt.Y(
                "HY OAS (%):Q",
                title="Spread (%)"
            ),
            tooltip=[
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip(
                    "HY OAS (%):Q",
                    title="HY OAS",
                    format=".2f"
                )
            ]
        ).interactive()

        st.altair_chart(
            chart_hy,
            width="stretch"
        )
        show_chart_month_caption()

    else:
        st.warning(
            "High Yield Credit Spread data not available."
        )

else:
    st.warning(
        "High Yield Credit Spread data not available."
    )










# Code was removed from here















st.subheader("SOFR vs FFR (Zoomed Spread View)")

# Melt data for Altair
rates_df = chart_df[["date", "SOFR", "FFR"]].melt(id_vars="date")

# Tight y-axis around the two series
min_rate = rates_df["value"].min()
max_rate = rates_df["value"].max()

# Expand slightly so lines aren’t on borders
padding = (max_rate - min_rate) * 0.5  # exaggerates spread visibility


# Make chart with axis_style and designate line colors red and blue
chart_rates = alt.Chart(rates_df).mark_line().encode(
    x=alt.X("date:T", axis=axis_style),
    y=alt.Y(
        "value:Q",
        scale=alt.Scale(domain=[min_rate - padding, max_rate + padding]),
        axis=axis_style
    ),
    color=alt.Color(
        "variable:N",
        scale=alt.Scale(
            domain=["SOFR", "FFR"],
            range=["red", "blue"]
        ),
        legend=alt.Legend(title="Rate")
    ),
    tooltip=["date:T", "variable:N", "value:Q"]
).interactive()


st.altair_chart(chart_rates, width="stretch")
show_chart_month_caption()

st.subheader("SOFR Spread (SOFR - FFR)")
# Ensure SOFR_Spread exists before plotting
if "SOFR_Spread" in master_df.columns:
    # For st.line_chart, the index must be datetime-like, which it is after ffill
    st.line_chart(chart_df[["date", "SOFR_Spread"]].set_index("date"))
    show_chart_month_caption()
else:
    st.warning("SOFR Spread data not available.")

st.subheader("Stablecoin Market Cap (USD) — Zoomed View")

sc_min = chart_df["Stablecoin Mkt Cap"].min()
sc_max = chart_df["Stablecoin Mkt Cap"].max()

# Add small padding so the line isn't touching edges
padding = (sc_max - sc_min) * 0.1

# Make chart with axis_style and pad scale
chart_stable = alt.Chart(chart_df).mark_line().encode(
    x=alt.X("date:T", axis=axis_style),
    y=alt.Y(
        "Stablecoin Mkt Cap:Q",
        scale=alt.Scale(domain=[sc_min - padding, sc_max + padding]),
        axis=axis_style
    ),
    tooltip=["date:T", "Stablecoin Mkt Cap:Q"]
).interactive()

st.altair_chart(chart_stable, width="stretch")
show_chart_month_caption()

# Show percent change in Stablecoin Market Cap chart
# Code was removed from here


# Optional: Altair interactive chart
import altair as alt

st.subheader("VIX Index Daily Price")

chart_vix = alt.Chart(chart_vix).mark_line().encode(
    x=alt.X("date:T", axis=axis_style),
    y=alt.Y("VIX:Q", axis=axis_style),
    tooltip=["date:T", "VIX:Q"]
).interactive()

st.altair_chart(chart_vix, width="stretch")
show_chart_month_caption()

# ------------------------
# SHEL Chart
# ------------------------
st.subheader("SHEL Daily Price")

chart_shel = alt.Chart(chart_shel).mark_line().encode(
    x=alt.X("date:T"),
    y=alt.Y(
        "SHEL:Q",
        scale=alt.Scale(zero=False)
    ),
    tooltip=["date:T", "SHEL:Q"]
).interactive()

st.altair_chart(chart_shel, width="stretch")
show_chart_month_caption()

st.subheader("SPY ETF Daily Price")

chart_spy = alt.Chart(chart_spy).mark_line().encode(
    x=alt.X("date:T"),
    y=alt.Y(
        "SPY:Q",
        scale=alt.Scale(domain=[600, 800])   # 👈 THIS IS THE KEY
    ),
    tooltip=["date:T", "SPY:Q"]
).interactive()

st.altair_chart(chart_spy, width="stretch")
show_chart_month_caption()

st.subheader("GLD ETF Daily Price")

chart_gld = alt.Chart(chart_gld).mark_line().encode(
    x=alt.X("date:T"),
    y=alt.Y(
        "GLD:Q",
        scale=alt.Scale(zero=False)  # keeps movement visible
    ),
    tooltip=["date:T", "GLD:Q"]
).interactive()

st.altair_chart(chart_gld, width="stretch")
show_chart_month_caption()

# ------------------------
# VTIP Chart
# ------------------------
st.subheader("VTIP ETF Daily Price")

chart_vtip = alt.Chart(chart_vtip).mark_line().encode(
    x=alt.X("date:T"),
    y=alt.Y(
        "VTIP:Q",
        scale=alt.Scale(zero=False)
    ),
    tooltip=["date:T", "VTIP:Q"]
).interactive()

st.altair_chart(chart_vtip, width="stretch")
show_chart_month_caption()


# ------------------------
# TLT Chart
# ------------------------
st.subheader("TLT ETF Daily Price")

chart_tlt = alt.Chart(chart_tlt).mark_line().encode(
    x=alt.X("date:T"),
    y=alt.Y(
        "TLT:Q",
        scale=alt.Scale(zero=False)
    ),
    tooltip=["date:T", "TLT:Q"]
).interactive()

st.altair_chart(chart_tlt, width="stretch")
show_chart_month_caption()


# ------------------------
# CRCL Chart
# ------------------------
st.subheader("CRCL Daily Price")

chart_crcl = alt.Chart(chart_crcl).mark_line().encode(
    x=alt.X("date:T"),
    y=alt.Y(
        "CRCL:Q",
        scale=alt.Scale(zero=False)
    ),
    tooltip=["date:T", "CRCL:Q"]
).interactive()

st.altair_chart(chart_crcl, width="stretch")
show_chart_month_caption()


# ------------------------
# DRAM Chart
# ------------------------
st.subheader("DRAM Daily Price")

# Corrected DRAM processing to ensure datetime.date objects
# The standardize_yf_df function should have already handled this,
# but double-checking here with apply is a safeguard against lingering Timestamps.
# In this version, standardize_yf_df is used for all yf downloads, so this apply
# might be redundant IF standardize_yf_df correctly produces datetime.date.
# Let's rely on standardize_yf_df first. If it still fails, uncomment the apply line.
# dram['date'] = dram['date'].apply(lambda x: x.date() if isinstance(x, pd.Timestamp) else x)


chart_dram = alt.Chart(chart_dram).mark_line().encode(
    x=alt.X("date:T", axis=axis_style),
    y=alt.Y(
        "DRAM:Q",
        axis=axis_style
    ),
    tooltip=["date:T", "DRAM:Q"]
).interactive()

st.altair_chart(chart_dram, width="stretch")
show_chart_month_caption()


# ------------------------
# JNK Chart
# ------------------------
st.subheader("JNK ETF Daily Price")

chart_jnk = alt.Chart(chart_jnk).mark_line().encode(
    x=alt.X("date:T"),
    y=alt.Y(
        "JNK:Q",
        scale=alt.Scale(zero=False)
    ),
    tooltip=["date:T", "JNK:Q"]
).interactive()

st.altair_chart(chart_jnk, width="stretch")
show_chart_month_caption()


# ------------------------
# EMB Chart
# ------------------------
st.subheader("EMB ETF Daily Price")

chart_emb = alt.Chart(chart_emb).mark_line().encode(
    x=alt.X("date:T"),
    y=alt.Y(
        "EMB:Q",
        scale=alt.Scale(zero=False)
    ),
    tooltip=["date:T", "EMB:Q"]
).interactive()

st.altair_chart(chart_emb, width="stretch")
show_chart_month_caption()

# ------------------------
# US Dollar Index Charts (from FRED) made conditional with 'no data available warning'
# ------------------------
st.subheader("US Dollar Index (Proxy – DTWEXBGS)")

if chart_df["DTWEXBGS"].notna().any():
    dtw_min = chart_df["DTWEXBGS"].min()
    dtw_max = chart_df["DTWEXBGS"].max()
    pad = (dtw_max - dtw_min) * 0.05

    chart_usd_proxy = alt.Chart(chart_df).mark_line().encode(
        x=alt.X("date:T", axis=axis_style),
        y=alt.Y(
            "DTWEXBGS:Q",
            scale=alt.Scale(domain=[dtw_min - pad, dtw_max + pad]),
            axis=axis_style
        ),
        tooltip=["date:T", "DTWEXBGS:Q"]
    ).interactive()

    st.altair_chart(chart_usd_proxy, use_container_width=True)
    show_chart_month_caption()
else:
    st.warning("🚫 No USD proxy index data (FRED rate‑limit).")

# Make chart USD inflation adjusted, conditional with 'no data available warning'
st.subheader("US Dollar Index (Inflation Adjusted – RTWEXBGS)")

if chart_df["RTWEXBGS"].notna().any():
    rtw_min = chart_df["RTWEXBGS"].min()
    rtw_max = chart_df["RTWEXBGS"].max()
    pad = (rtw_max - rtw_min) * 0.05

    chart_usd_infl = alt.Chart(chart_df).mark_line().encode(
        x=alt.X("date:T", axis=axis_style),
        y=alt.Y(
            "RTWEXBGS:Q",
            scale=alt.Scale(domain=[rtw_min - pad, rtw_max + pad]),
            axis=axis_style
        ),
        tooltip=["date:T", "RTWEXBGS:Q"]
    ).interactive()

    st.altair_chart(chart_usd_infl, use_container_width=True)
    show_chart_month_caption()
else:
    st.warning("🚫 No inflation‑adjusted USD index data (FRED rate‑limit).")


# NEW: Add a chart for JPYUSD
st.subheader("Japanese Yen vs US Dollar (JPY=X)")

# Calculate dynamic padding for the y-axis scale for JPYUSD
jpyusd_min = chart_df["JPYUSD"].min()
jpyusd_max = chart_df["JPYUSD"].max()
padding_jpyusd = (jpyusd_max - jpyusd_min) * 0.05

chart_jpyusd = alt.Chart(chart_df).mark_line().encode(
    x=alt.X("date:T", axis=axis_style),
    y=alt.Y(
        "JPYUSD:Q",
        scale=alt.Scale(domain=[jpyusd_min - padding_jpyusd, jpyusd_max + padding_jpyusd]),
        axis=axis_style
    ),
    tooltip=["date:T", "JPYUSD:Q"]
).interactive()

st.altair_chart(chart_jpyusd, width="stretch")
show_chart_month_caption()


# ------------------------
# AAVE USDC SUPPLY APY
# ------------------------
if "USDC Supply APY" in master_df.columns:

    st.subheader("Aave USDC Supply APY")

    aave_df = chart_df.dropna(
        subset=["USDC Supply APY"]
    )

    if not aave_df.empty:

        apy_min = aave_df["USDC Supply APY"].min()
        apy_max = aave_df["USDC Supply APY"].max()

        padding = max(
            (apy_max - apy_min) * 0.10,
            0.05
        )

        chart_aave_supply = (
            alt.Chart(aave_df)
            .mark_line()
            .encode(
                x=alt.X(
                    "date:T",
                    axis=axis_style
                ),
                y=alt.Y(
                    "USDC Supply APY:Q",
                    scale=alt.Scale(
                        domain=[
                            apy_min - padding,
                            apy_max + padding
                        ]
                    ),
                    axis=axis_style
                ),
                tooltip=[
                    alt.Tooltip(
                        "date:T"
                    ),
                    alt.Tooltip(
                        "USDC Supply APY:Q",
                        format=".2f"
                    )
                ]
            )
            .interactive()
        )

        st.altair_chart(
            chart_aave_supply,
            width="stretch"
        )
        show_chart_month_caption()

# Standalone Aave API test block omitted in the hosted dashboard to avoid a duplicate request.
