
import os
import time
import threading
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================
# ENV VARIABLES
# ==========================================

TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"

PORT = int(os.getenv("PORT", 10000))

# ==========================================
# CONFIG
# ==========================================

CONFIG = {

    "min_score": 85,

    "min_volume_usdt": 3_000_000,

    "min_volume_spike": 2.0,

    "cooldown_minutes": 45,

    "max_active_trades": 5,

    "atr_tp1": 1.5,

    "atr_tp2": 3.0,

    "atr_sl": 1.8,

    "rsi_min": 55,

    "rsi_max": 72,

    "scan_interval": 1800,

    "monitor_interval": 10,
}

# ==========================================
# GLOBALS
# ==========================================

active_trades = {}

cooldowns = {}

# ==========================================
# TELEGRAM
# ==========================================

def send_telegram(message):

    try:

        url = (
            f"https://api.telegram.org/bot"
            f"{TOKEN}/sendMessage"
        )

        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }

        response = requests.post(
            url,
            json=payload,
            timeout=10
        )

        print(response.text)

    except Exception as e:

        print(f"Telegram Error: {e}")

# ==========================================
# INDICATORS
# ==========================================

def compute_ema(series, length):

    return (
        series
        .ewm(span=length, adjust=False)
        .mean()
    )

def compute_rsi(series, length=14):

    delta = series.diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = (
        gain
        .rolling(length)
        .mean()
    )

    avg_loss = (
        loss
        .rolling(length)
        .mean()
    )

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))

def compute_atr(high, low, close, length=14):

    tr1 = high - low

    tr2 = abs(high - close.shift())

    tr3 = abs(low - close.shift())

    tr = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    return tr.rolling(length).mean()

def compute_adx(df, period=14):

    high = df['high']

    low = df['low']

    close = df['close']

    plus_dm = high.diff()

    minus_dm = low.diff().abs()

    plus_dm[plus_dm < 0] = 0

    minus_dm[minus_dm < 0] = 0

    tr1 = high - low

    tr2 = abs(high - close.shift())

    tr3 = abs(low - close.shift())

    tr = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    atr = tr.rolling(period).mean()

    plus_di = (
        100
        * plus_dm.rolling(period).mean()
        / atr
    )

    minus_di = (
        100
        * minus_dm.rolling(period).mean()
        / atr
    )

    dx = (
        abs(plus_di - minus_di)
        / (plus_di + minus_di)
    ) * 100

    return dx.rolling(period).mean()

# ==========================================
# BINANCE DATA
# ==========================================

def get_binance_data(
    symbol,
    interval='15m',
    limit=300
):

    try:

        url = (
            "https://api.binance.com/api/v3/klines"
            f"?symbol={symbol}"
            f"&interval={interval}"
            f"&limit={limit}"
        )

        response = requests.get(
            url,
            timeout=10
        )

        data = response.json()

        if not isinstance(data, list):

            return pd.DataFrame()

        df = pd.DataFrame(data, columns=[
            'time',
            'open',
            'high',
            'low',
            'close',
            'vol',
            'c_time',
            'q_v',
            'tr',
            'tb',
            'tq',
            'i'
        ])

        cols = [
            'open',
            'high',
            'low',
            'close',
            'vol'
        ]

        df[cols] = df[cols].astype(float)

        df['ema20'] = compute_ema(df['close'], 20)

        df['ema50'] = compute_ema(df['close'], 50)

        df['ema200'] = compute_ema(df['close'], 200)

        df['rsi'] = compute_rsi(df['close'])

        df['atr'] = compute_atr(
            df['high'],
            df['low'],
            df['close']
        )

        df['adx'] = compute_adx(df)

        df['vol_sma'] = (
            df['vol']
            .rolling(20)
            .mean()
        )

        return df.dropna()

    except Exception as e:

        print(f"{symbol} ERROR: {e}")

        return pd.DataFrame()

# ==========================================
# TOP COINS
# ==========================================

def get_top_coins():

    try:

        url = (
            "https://api.coingecko.com/api/v3/"
            "coins/markets"
            "?vs_currency=usd"
            "&order=market_cap_desc"
            "&per_page=50"
            "&page=1"
        )

        data = requests.get(
            url,
            timeout=15
        ).json()

        return [
            coin['symbol'].upper() + "USDT"
            for coin in data
            if coin['symbol'].isalpha()
        ]

    except:

        return [
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT",
            "BNBUSDT"
        ]

# ==========================================
# SCORE
# ==========================================

def calculate_score(df):

    if df.empty:
        return 0

    last = df.iloc[-1]

    score = 0

    if last['close'] > last['ema200']:
        score += 25

    if last['ema20'] > last['ema50']:
        score += 20

    if (
        CONFIG['rsi_min']
        < last['rsi']
        < CONFIG['rsi_max']
    ):
        score += 15

    vol_ratio = (
        last['vol']
        / last['vol_sma']
    )

    if vol_ratio >= CONFIG['min_volume_spike']:
        score += 20

    usdt_volume = (
        last['vol']
        * last['close']
    )

    if usdt_volume >= CONFIG['min_volume_usdt']:
        score += 10

    if last['adx'] > 22:
        score += 10

    return min(score, 100)

# ==========================================
# MTF FILTER
# ==========================================

def multi_timeframe_filter(symbol):

    try:

        df15 = get_binance_data(symbol, '15m')

        df1h = get_binance_data(symbol, '1h')

        if df15.empty or df1h.empty:
            return False

        last15 = df15.iloc[-1]

        last1h = df1h.iloc[-1]

        return (
            last15['ema20']
            > last15['ema50']
            and
            last1h['ema20']
            > last1h['ema50']
        )

    except:

        return False

# ==========================================
# COOLDOWN
# ==========================================

def is_on_cooldown(symbol):

    if symbol not in cooldowns:
        return False

    elapsed = (
        datetime.now()
        - cooldowns[symbol]
    ).seconds / 60

    return (
        elapsed
        < CONFIG['cooldown_minutes']
    )

# ==========================================
# SIGNAL
# ==========================================

def send_signal(
    symbol,
    entry,
    tp1,
    tp2,
    sl,
    score
):

    msg = f"""
🚀 *HIGH PROBABILITY SCALP*

💎 {symbol}

🤖 AI SCORE: {score}/100

💰 ENTRY: {entry:.4f}

🎯 TP1: {tp1:.4f}

🎯 TP2: {tp2:.4f}

🛑 SL: {sl:.4f}

🔥 Trend Confirmed
"""

    send_telegram(msg)

# ==========================================
# SCAN MARKET
# ==========================================

def scan_market():

    print(f"[{datetime.now()}] SCANNING")

    if len(active_trades) >= CONFIG['max_active_trades']:
        return

    symbols = get_top_coins()

    for symbol in symbols[:40]:

        try:

            if symbol in active_trades:
                continue

            if is_on_cooldown(symbol):
                continue

            if not multi_timeframe_filter(symbol):
                continue

            df = get_binance_data(symbol)

            if df.empty:
                continue

            score = calculate_score(df)

            if score < CONFIG['min_score']:
                continue

            last = df.iloc[-1]

            entry = last['close']

            atr = last['atr']

            tp1 = (
                entry
                + atr * CONFIG['atr_tp1']
            )

            tp2 = (
                entry
                + atr * CONFIG['atr_tp2']
            )

            sl = (
                entry
                - atr * CONFIG['atr_sl']
            )

            send_signal(
                symbol,
                entry,
                tp1,
                tp2,
                sl,
                score
            )

            active_trades[symbol] = {
                "entry": entry,
                "tp1": tp1,
                "tp2": tp2,
                "sl": sl
            }

            cooldowns[symbol] = datetime.now()

        except Exception as e:

            print(f"{symbol} SCAN ERROR: {e}")

# ==========================================
# MONITOR
# ==========================================

def monitor_trades():

    while True:

        try:

            for symbol in list(active_trades.keys()):

                trade = active_trades[symbol]

                df = get_binance_data(
                    symbol,
                    '1m',
                    5
                )

                if df.empty:
                    continue

                price = df['close'].iloc[-1]

                if price >= trade['tp2']:

                    send_telegram(
                        f"🏆 {symbol} TP2 HIT"
                    )

                    del active_trades[symbol]

                elif price <= trade['sl']:

                    send_telegram(
                        f"🛑 {symbol} STOP LOSS"
                    )

                    del active_trades[symbol]

        except Exception as e:

            print(f"MONITOR ERROR: {e}")

        time.sleep(
            CONFIG['monitor_interval']
        )

# ==========================================
# PERIODIC SCAN
# ==========================================

def periodic_scan():

    while True:

        scan_market()

        time.sleep(
            CONFIG['scan_interval']
        )

# ==========================================
# HEALTH CHECK
# ==========================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)

        self.end_headers()

        self.wfile.write(
            b"BOT IS RUNNING"
        )

def run_health():

    server = HTTPServer(
        ('0.0.0.0', PORT),
        HealthHandler
    )

    server.serve_forever()

# ==========================================
# MAIN
# ==========================================

def main():

    threading.Thread(
        target=run_health,
        daemon=True
    ).start()

    threading.Thread(
        target=monitor_trades,
        daemon=True
    ).start()

    threading.Thread(
        target=periodic_scan,
        daemon=True
    ).start()

    send_telegram(
        "✅ BOT STARTED SUCCESSFULLY"
    )

    print("BOT RUNNING")

    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()if __name__ == "__main__":
    main()