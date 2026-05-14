#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت سكالبينغ – يعمل فوراً ويرسل صفقات كثيرة
"""

import os
import time
import json
import threading
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# ========== إعداداتك ==========
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
PORT = int(os.getenv("PORT", 10000))

# إعدادات خفيفة جداً (لإرسال صفقات فورية)
CONFIG = {
    "min_volume_usdt": 10_000,
    "min_volume_spike": 1.0,
    "min_score": 10,
    "cooldown_minutes": 1,
    "atr_multiplier_tp1": 1.2,
    "atr_multiplier_tp2": 2.2,
    "atr_multiplier_sl": 1.2,
}

# ========== إرسال رسالة إلى تليجرام ==========
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"خطأ: {e}")

# ========== المؤشرات الفنية ==========
def compute_ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def compute_rsi(series, length=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=length, min_periods=length).mean()
    avg_loss = loss.rolling(window=length, min_periods=length).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def compute_atr(high, low, close, length=14):
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=length).mean()

def get_binance_data(symbol, interval='15m', limit=300):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    data = requests.get(url, timeout=10).json()
    df = pd.DataFrame(data, columns=['time','open','high','low','close','vol','c_time','q_v','tr','tb','tq','i']).astype(float)
    df['ema20'] = compute_ema(df['close'], 20)
    df['ema50'] = compute_ema(df['close'], 50)
    df['ema200'] = compute_ema(df['close'], 200)
    df['rsi'] = compute_rsi(df['close'], 14)
    df['atr'] = compute_atr(df['high'], df['low'], df['close'], 14)
    df['vol_sma'] = df['vol'].rolling(window=20).mean()
    return df

def calculate_score(df):
    if df.empty:
        return 0
    last = df.iloc[-1]
    score = 0
    if last['close'] > last['ema200']:
        score += 25
    if last['ema20'] > last['ema50']:
        score += 20
    if 55 < last['rsi'] < 75:
        score += 20
    vol_ratio = last['vol'] / last['vol_sma'] if last['vol_sma'] != 0 else 1
    if vol_ratio > CONFIG['min_volume_spike']:
        score += 20
    if last['vol'] * last['close'] > CONFIG['min_volume_usdt']:
        score += 15
    return min(100, score)

# ========== أفضل 100 عملة ==========
def get_top_100_coins():
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false"
        data = requests.get(url, timeout=15).json()
        return [item['symbol'].upper() + 'USDT' for item in data if item['symbol'].isalpha()][:50]
    except:
        return ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT","DOTUSDT","LINKUSDT"]

# ========== فحص السوق وإرسال الإشارات ==========
def scan_market():
    print(f"[{datetime.now()}] بدء الفحص...")
    symbols = get_top_100_coins()
    for sym in symbols[:30]:
        try:
            df = get_binance_data(sym)
            if df.empty:
                continue
            score = calculate_score(df)
            if score >= CONFIG['min_score']:
                last = df.iloc[-1]
                entry = last['close']
                atr = last['atr']
                tp1 = entry + atr * CONFIG['atr_multiplier_tp1']
                tp2 = entry + atr * CONFIG['atr_multiplier_tp2']
                sl = entry - atr * CONFIG['atr_multiplier_sl']
                msg = (
                    f"🚀 *إشارة سكالبينغ* 🚀\n\n"
                    f"💎 {sym}\n"
                    f"🤖 AI Score: {score}/100\n"
                    f"💰 الدخول: {entry:.4f}\n"
                    f"🎯 TP1: {tp1:.4f} (+{(tp1/entry-1)*100:.2f}%)\n"
                    f"🎯 TP2: {tp2:.4f} (+{(tp2/entry-1)*100:.2f}%)\n"
                    f"🛑 SL: {sl:.4f} (-{(1-sl/entry)*100:.2f}%)"
                )
                send_telegram(msg)
                print(f"تم إرسال إشارة لـ {sym}")
                time.sleep(CONFIG['cooldown_minutes'] * 60)
        except Exception as e:
            print(f"خطأ: {e}")

def periodic_scan():
    while True:
        time.sleep(1800)
        scan_market()

# ========== خادم الصحة ==========
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")
def run_health():
    server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
    server.serve_forever()

# ========== التشغيل ==========
def main():
    threading.Thread(target=run_health, daemon=True).start()
    threading.Thread(target=periodic_scan, daemon=True).start()
    send_telegram("✅ البوت يعمل (نسخة خفيفة) – سيرسل إشارات كثيرة فوراً")
    scan_market()  # فحص فوري
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()