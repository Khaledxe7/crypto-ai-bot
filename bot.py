#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت سكالبينغ - يرسل رسالة فورية عند التشغيل وإشارات كثيرة
"""

import os
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

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
}

# ========== إرسال رسالة إلى تليجرام ==========
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
        print(f"إرسال: {r.status_code} - {message[:50]}")
    except Exception as e:
        print(f"خطأ إرسال: {e}")

# ========== مؤشرات بسيطة ==========
def get_binance_data(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=100"
    data = requests.get(url, timeout=10).json()
    df = pd.DataFrame(data, columns=['time','open','high','low','close','vol','c_time','q_v','tr','tb','tq','i']).astype(float)
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    # RSI بسيط
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['vol_sma'] = df['vol'].rolling(window=20).mean()
    return df

def calculate_score(df):
    if df.empty:
        return 0
    last = df.iloc[-1]
    score = 0
    if last['close'] > last['ema200']:
        score += 30
    if last['ema20'] > last['ema50']:
        score += 30
    if 40 < last['rsi'] < 80:
        score += 20
    if last['vol'] > last['vol_sma']:
        score += 20
    return min(100, score)

# ========== قائمة عملات ==========
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    "MATICUSDT", "NEARUSDT", "FETUSDT", "RNDRUSDT", "ATOMUSDT"
]

# ========== فحص وإرسال ==========
def scan_and_send():
    print(f"[{datetime.now()}] بدء الفحص...")
    for sym in SYMBOLS:
        try:
            df = get_binance_data(sym)
            if df.empty:
                continue
            score = calculate_score(df)
            if score >= CONFIG['min_score']:
                last = df.iloc[-1]
                entry = last['close']
                msg = (
                    f"🚀 *إشارة سكالبينغ* 🚀\n\n"
                    f"💎 {sym}\n"
                    f"🤖 AI Score: {score}/100\n"
                    f"💰 السعر: {entry:.4f}\n"
                    f"📈 المؤشرات: إيجابية\n"
                    f"✅ فرصة شراء موصى بها"
                )
                send_telegram(msg)
                print(f"✓ تم إرسال إشارة لـ {sym}")
                time.sleep(CONFIG['cooldown_minutes'] * 60)
        except Exception as e:
            print(f"خطأ في {sym}: {e}")

# ========== فحص دوري ==========
def periodic_scan():
    while True:
        time.sleep(1800)  # 30 دقيقة
        scan_and_send()

# ========== خادم الصحة لـ Render ==========
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")
def run_health():
    server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
    server.serve_forever()

# ========== التشغيل الرئيسي ==========
def main():
    # 1. تشغيل خادم الصحة
    threading.Thread(target=run_health, daemon=True).start()
    
    # 2. إرسال رسالة فورية فور بدء التشغيل
    send_telegram("✅ *البوت شغال الآن!* سيبدأ فحص السوق فوراً وإرسال الإشارات.")
    
    # 3. بدء الفحص الدوري
    threading.Thread(target=periodic_scan, daemon=True).start()
    
    # 4. فحص فوري أول مرة
    scan_and_send()
    
    # 5. البقاء قيد التشغيل
    print("البوت يعمل...")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()