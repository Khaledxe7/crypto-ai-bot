#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import threading
import requests
import pandas as pd
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================
# TELEGRAM CONFIG
# ==========================================

TOKEN = os.getenv("8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs")
CHAT_ID = os.getenv("900307207")

PORT = int(os.getenv("PORT", 10000))

# ==========================================
# BOT CONFIG
# ==========================================

CONFIG = {

    "min_score": 85,

    "min_volume_usdt": 3000000,

    "min_volume_spike": 2.0,

    "cooldown_minutes": 45,

    "scan_interval": 1800,

    "monitor_interval": 10,

    "atr_tp1": 1.5,

    "atr_tp2": 3.0,

    "atr_sl": 1.8,

    "rsi_min": 55,

    "rsi_max": 72,
}

# ==========================================
# GLOBAL VARIABLES
# ==========================================

active_trades = {}

cooldowns = {}

# ==========================================
# TELEGRAM MESSAGE
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
# EMA
# ==========================================

def compute_ema(series, length):

    return (
        series
        .ewm(span=length, adjust=False)
        .mean()
    )

# ==========================================
# RSI
# ==========================================

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

    rsi = 100 - (100 / (1 + rs))

    return rsi

# ==========================================
# ATR
# ==========================================

def compute_atr(high, low, close, length=14):

    tr1 = high - low

    tr2 = abs(high - close.shift())

    tr3 = abs(low - close.shift())

    tr = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    atr = tr.rolling(length).mean()

    return atr

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

            'volume',

            'c_time',

            'q_v',

            'tr',

            'tb',

            'tq',

            'i'
        ])

        numeric_cols = [

            'open',

            'high',

            'low',

            'close',

            'volume'
        ]

        df[numeric_cols] = (
            df[numeric_cols]
            .astype(float)
        )

        # INDICATORS

        df['ema20'] = compute_ema(
            df['close'],
            20
        )

        df['ema50'] = compute_ema(
            df['close'],
            50
        )

        df['ema200'] = compute_ema(
            df['close'],
            200
        )

        df['rsi'] = compute_rsi(
            df['close']
        )

        df['atr'] = compute_atr(
            df['high'],
            df['low'],
            df['close']
        )

        df['vol_sma'] = (
            df['volume']
            .rolling(20)
            .mean()
        )

        return df.dropna()

    except Exception as e:

        print(f"{symbol} ERROR: {e}")

        return pd.DataFrame()

# ==========================================
# GET TOP COINS
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

        response = requests.get(
            url,
            timeout=10
        )

        data = response.json()

        symbols = []

        for coin in data:

            symbol = (
                coin['symbol']
                .upper()
            )

            symbols.append(
                symbol + "USDT"
            )

        return symbols[:30]

    except:

        return [

            "BTCUSDT",

            "ETHUSDT",

            "SOLUSDT",

            "BNBUSDT",

            "XRPUSDT"
        ]

# ==========================================
# SCORE SYSTEM
# ==========================================

def calculate_score(df):

    if df.empty:

        return 0

    last = df.iloc[-1]

    score = 0

    # TREND

    if last['close'] > last['ema200']:

        score += 25

    if last['ema20'] > last['ema50']:

        score += 20

    # RSI

    if (
        CONFIG['rsi_min']
        < last['rsi']
        < CONFIG['rsi_max']
    ):

        score += 20

    # VOLUME SPIKE

    vol_ratio = (
        last['volume']
        / last['vol_sma']
    )

    if vol_ratio >= CONFIG['min_volume_spike']:

        score += 20

    # LIQUIDITY

    usdt_volume = (
        last['volume']
        * last['close']
    )

    if usdt_volume >= CONFIG['min_volume_usdt']:

        score += 15

    return min(score, 100)

# ==========================================
# COOLDOWN CHECK
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
# SEND SIGNAL
# ==========================================

def send_signal(
    symbol,
    entry,
    tp1,
    tp2,
    sl,
    score
):

    message = f"""
🚀 HIGH PROBABILITY SCALP

💎 {symbol}

🤖 SCORE: {score}/100

💰 ENTRY: {entry:.4f}

🎯 TP1: {tp1:.4f}

🎯 TP2: {tp2:.4f}

🛑 SL: {sl:.4f}

🔥 TREND CONFIRMED
"""

    send_telegram(message)

# ==========================================
# MARKET SCAN
# ==========================================

def scan_market():

    print(f"[{datetime.now()}] SCANNING MARKET")

    symbols = get_top_coins()

    for symbol in symbols:

        try:

            if symbol in active_trades:

                continue

            if is_on_cooldown(symbol):

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

            print(f"SIGNAL SENT: {symbol}")

        except Exception as e:

            print(f"{symbol} ERROR: {e}")

# ==========================================
# MONITOR TRADES
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

                # TAKE PROFIT

                if price >= trade['tp2']:

                    send_telegram(
                        f"🏆 {symbol} TP2 HIT"
                    )

                    del active_trades[symbol]

                # STOP LOSS

                elif price <= trade['sl']:

                    send_telegram(
                        f"🛑 {symbol} STOP LOSS HIT"
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
# HEALTH SERVER
# ==========================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)

        self.end_headers()

        self.wfile.write(
            b"BOT RUNNING"
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

    # HEALTH CHECK

    threading.Thread(
        target=run_health,
        daemon=True
    ).start()

    # MONITOR

    threading.Thread(
        target=monitor_trades,
        daemon=True
    ).start()

    # MARKET SCAN

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

# ==========================================
# START
# ==========================================

if __name__ == "__main__":
    main()