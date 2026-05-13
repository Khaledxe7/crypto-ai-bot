#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت سكالبينغ متكامل - يعمل على Render بدون مشاكل
يستخدم requests فقط لإرسال الإشعارات
"""

import os
import time
import json
import asyncio
import logging
import requests
import pandas as pd
import numpy as np
import feedparser
import yfinance as yf
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# ========== إعداداتك ==========
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
PORT = int(os.getenv("PORT", 10000))

# إعدادات التداول
CONFIG = {
    "min_volume_usdt": 500_000,
    "min_volume_spike": 1.2,
    "min_score": 40,
    "cooldown_minutes": 5,
    "atr_multiplier_tp1": 1.2,
    "atr_multiplier_tp2": 2.2,
    "atr_multiplier_sl": 1.2,
}

# ========== إرسال رسالة إلى تليجرام ==========
def send_telegram(message):
    """إرسال رسالة عبر API المباشر لتليجرام"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ تم إرسال الرسالة")
        else:
            print(f"❌ فشل الإرسال: {response.text}")
    except Exception as e:
        print(f"❌ خطأ في الإرسال: {e}")

# ========== دوال المؤشرات الفنية ==========
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
        symbols = [item['symbol'].upper() + 'USDT' for item in data if item['symbol'].isalpha()]
        return symbols[:50]
    except:
        return ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT","DOTUSDT","LINKUSDT"]

# ========== البيانات الكلية ==========
def get_macro():
    try:
        dxy = yf.Ticker("DX-Y.NYB")
        dxy_data = dxy.history(period="1d")
        dollar = round(dxy_data['Close'].iloc[-1], 2) if not dxy_data.empty else 98.5
        gold = yf.Ticker("GC=F")
        gold_data = gold.history(period="1d")
        gold_price = round(gold_data['Close'].iloc[-1], 2) if not gold_data.empty else 2350.0
        return {"dollar": dollar, "gold": gold_price}
    except:
        return {"dollar": 98.5, "gold": 2350.0}

# ========== الأخبار العالمية ==========
def get_news():
    alerts = {"trump": "", "musk": "", "war": ""}
    try:
        feed = feedparser.parse("https://www.reuters.com/world/rss")
        for entry in feed.entries[:10]:
            title = entry.title.lower()
            if "trump" in title:
                alerts["trump"] = title[:80]
            if "elon" in title or "musk" in title:
                alerts["musk"] = title[:80]
            if any(w in title for w in ["taiwan", "hormuz", "iran", "china", "war"]):
                alerts["war"] = title[:80]
    except:
        pass
    return alerts

# ========== إدارة الصفقات ==========
active_trades = {}

def send_signal(symbol, entry, tp1, tp2, sl, score, macro, news):
    msg = (
        f"🚀 *إشارة سكالبينغ* 🚀\n\n"
        f"💎 {symbol}\n"
        f"🤖 AI Score: {score}/100\n"
        f"💰 الدخول: {entry:.4f}\n"
        f"🎯 TP1: {tp1:.4f} (+{(tp1/entry-1)*100:.2f}%)\n"
        f"🎯 TP2: {tp2:.4f} (+{(tp2/entry-1)*100:.2f}%)\n"
        f"🛑 SL: {sl:.4f} (-{(1-sl/entry)*100:.2f}%)\n"
        f"💵 الدولار: {macro['dollar']} | 🥇 الذهب: ${macro['gold']}\n"
        f"📰 ترامب: {news['trump'][:50]}\n"
        f"📰 ماسك: {news['musk'][:50]}\n"
        f"⚔️ حروب: {news['war'][:50]}"
    )
    send_telegram(msg)
    active_trades[symbol] = {"entry": entry, "tp1": tp1, "tp2": tp2, "sl": sl, "open_time": datetime.now()}

def scan_market():
    print(f"[{datetime.now()}] بدء فحص السوق...")
    TOP_SYMBOLS = get_top_100_coins()
    macro = get_macro()
    news = get_news()
    for sym in TOP_SYMBOLS[:30]:
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
                send_signal(sym, entry, tp1, tp2, sl, score, macro, news)
                time.sleep(CONFIG['cooldown_minutes'] * 60)
                break
        except Exception as e:
            print(f"خطأ في {sym}: {e}")
    print(f"[{datetime.now()}] انتهى الفحص.")

def monitor_trades():
    while True:
        for sym, trade in list(active_trades.items()):
            try:
                df = get_binance_data(sym, interval='1m', limit=5)
                if df.empty:
                    continue
                price = df['close'].iloc[-1]
                profit = (price - trade['entry']) / trade['entry']
                if price >= trade['tp2'] and not trade.get('closed'):
                    trade['closed'] = True
                    send_telegram(f"🏆 {sym} حقق TP2! الربح: {profit*100:.2f}%")
                    del active_trades[sym]
                elif price <= trade['sl'] and not trade.get('closed'):
                    trade['closed'] = True
                    loss = (trade['entry']-price)/trade['entry']*100
                    send_telegram(f"🛑 {sym} ضرب الستوب! الخسارة: {loss:.2f}%")
                    del active_trades[sym]
                elif price >= trade['tp1'] and not trade.get('tp1_hit'):
                    trade['tp1_hit'] = True
                    send_telegram(f"🎯 {sym} حقق TP1 (+{profit*100:.2f}%)")
            except:
                pass
        time.sleep(10)

def periodic_scan():
    while True:
        time.sleep(1800)  # 30 دقيقة
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

# ========== التشغيل الرئيسي ==========
def main():
    # بدء خادم الصحة
    threading.Thread(target=run_health, daemon=True).start()
    
    # إرسال رسالة بدء التشغيل
    send_telegram("✅ *البوت يعمل الآن (النسخة النهائية)*\nسيرسل إشارات عند العثور على فرص. سيتم الفحص التلقائي كل 30 دقيقة.")
    
    # بدء المهام
    threading.Thread(target=monitor_trades, daemon=True).start()
    threading.Thread(target=periodic_scan, daemon=True).start()
    
    # فحص أولي فوراً
    scan_market()
    
    # الإبقاء على التشغيل
    print("البوت يعمل...")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()