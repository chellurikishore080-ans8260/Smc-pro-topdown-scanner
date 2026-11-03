import streamlit as st
import pandas as pd
import requests
import concurrent.futures
from datetime import datetime

st.set_page_config(page_title="SMC Pro Scanner (1D -> 4H -> 15m)", layout="wide")
st.title("📊 SMC Pro Top-Down Scanner (1D/4H/15m)")

# API Hosts as per your screenshot logic
SPOT_HOSTS = [
    "https://api.binance.com",
    "https://data-api.binance.vision",
    "https://api1.binance.com"
]
FUT_HOSTS = ["https://fapi.binance.com"]

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT"]

def fetch_klines(symbol, interval, limit=50):
    """Try Futures API first, fallback to Spot Hosts if it fails"""
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    
    # Try Futures
    try:
        res = requests.get(f"{FUT_HOSTS[0]}/fapi/v1/klines", params=params, timeout=3)
        if res.status_code == 200:
            return process_data(res.json())
    except:
        pass

    # Fallback to Spot
    for host in SPOT_HOSTS:
        try:
            res = requests.get(f"{host}/api/v3/klines", params=params, timeout=3)
            if res.status_code == 200:
                return process_data(res.json())
        except:
            continue
    return pd.DataFrame()

def process_data(data):
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'vol', 'ct', 'qav', 'nt', 'tbv', 'tqv', 'ig'])
    df = df[['timestamp', 'open', 'high', 'low', 'close']]
    for col in ['open', 'high', 'low', 'close']:
        df[col] = df[col].astype(float)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def get_1d_levels(df):
    """Finds Daily Swing Highs and Lows (Liquidity Pools & Naked Wicks)"""
    recent_high = df['high'].rolling(window=5, center=True).max().iloc[-3]
    recent_low = df['low'].rolling(window=5, center=True).min().iloc[-3]
    return recent_high, recent_low

def get_4h_fvgs(df):
    """Finds 4H FVGs (Points of Interest)"""
    fvgs = []
    for i in range(1, len(df)-1):
        if df['low'].iloc[i+1] > df['high'].iloc[i-1] and df['close'].iloc[i] > df['open'].iloc[i]:
            fvgs.append({'type': 'Bullish FVG', 'top': df['low'].iloc[i+1], 'bottom': df['high'].iloc[i-1]})
        elif df['high'].iloc[i+1] < df['low'].iloc[i-1] and df['close'].iloc[i] < df['open'].iloc[i]:
            fvgs.append({'type': 'Bearish FVG', 'top': df['low'].iloc[i-1], 'bottom': df['high'].iloc[i+1]})
    return fvgs

def analyze_symbol(symbol):
    df_1d = fetch_klines(symbol, "1d", 30)
    df_4h = fetch_klines(symbol, "4h", 30)
    df_15m = fetch_klines(symbol, "15m", 10)
    
    if df_1d.empty or df_4h.empty or df_15m.empty:
        return None
        
    daily_high, daily_low = get_1d_levels(df_1d)
    fvgs_4h = get_4h_fvgs(df_4h)
    
    if not fvgs_4h:
        return None
        
    latest_15m = df_15m.iloc[-1]
    last_fvg = fvgs_4h[-1]
    
    signal = "Wait (No Setup)"
    condition = ""
    
    # Check if 15m price is in 4H FVG
    in_zone = last_fvg['bottom'] <= latest_15m['close'] <= last_fvg['top']
    
    if in_zone:
        if last_fvg['type'] == 'Bullish FVG' and latest_15m['close'] > latest_15m['open']:
            signal = "🟢 BUY SETUP"
            condition = "15m Thrust from 4H Bullish FVG"
        elif last_fvg['type'] == 'Bearish FVG' and latest_15m['close'] < latest_15m['open']:
            signal = "🔴 SELL SETUP"
            condition = "15m Thrust from 4H Bearish FVG"
            
    return {
        "Symbol": symbol,
        "Daily High (Liq)": round(daily_high, 4),
        "Daily Low (Liq)": round(daily_low, 4),
        "4H POI Zone": f"{round(last_fvg['bottom'],4)} - {round(last_fvg['top'],4)} ({last_fvg['type'][:4]})",
        "15m Current": round(latest_15m['close'], 4),
        "Status / Signal": signal,
        "Logic": condition if condition else "Waiting for MSB/Thrust"
    }

if st.button("Scan Top-Down SMC Setup"):
    with st.spinner('Fetching 1D, 4H, and 15m data with Fallback APIs...'):
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_symbol = {executor.submit(analyze_symbol, sym): sym for sym in SYMBOLS}
            for future in concurrent.futures.as_completed(future_to_symbol):
                res = future.result()
                if res:
                    results.append(res)
                    
        if results:
            df_res = pd.DataFrame(results)
            st.dataframe(df_res, use_container_width=True)
            
st.markdown("---")
st.markdown("🎯 **Logic Integrated:** 1D Chart for Liquidity Sweep Levels -> 4H for FVG (Order Flow) -> 15m for Rejection/Thrust Candle Entry.")
