#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت سكالبينغ - فحص مستمر كل 60 ثانية
إشارات متوسطة الجودة (ليست كثيرة ولا صارمة جداً)
"""

import os
import time
import requests
import pandas as pd
import numpy as np
import feedparser
import yfinance as yf
from datetime import datetime
import threading

# ========== بياناتك ==========
TOKEN = "8497098367:AAFUMHaUs90r1V3KB_8_8HFWBv1ZHMfUhhM"
CHAT_ID = "900307207"

# إعدادات متوسطة (ليست صارمة جداً، وليست فضفاضة)
CONFIG = {
    "min_volume_usdt": 500_000,      # سيولة نصف مليون
    "min_volume_spike": 1.3,         # حجم أعلى من المتوسط بـ 30%
    "min_score": 65,                 # درجة جيدة (متوسطة)
    "cooldown_seconds": 3600,        # انتظر ساعة قبل إرسال إشارة لنفس العملة
    "atr_multiplier_tp1": 1.2,
    "atr_multiplier_tp2": 2.2,
    "atr_multiplier_sl": 1.2,
}

active_trades = {}
last_signal_time = {}  # لمنع تكرار الإشارة لنفس العملة

# ========== إرسال رسالة ==========
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
        print(f"✅ إرسال: {r.status_code}")
        return True
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return False

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
    try:
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
    except Exception as e:
        print(f"خطأ في {symbol}: {e}")
        return pd.DataFrame()

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

# ========== الأخبار ==========
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

# ========== إرسال الإشارة ==========
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
    last_signal_time[symbol] = time.time()

# ========== فحص السوق (كل 60 ثانية) ==========
def continuous_scan():
    symbols = get_top_100_coins()
    macro = get_macro()
    news = get_news()
    
    print(f"[{datetime.now()}] بدء الفحص المستمر...")
    for sym in symbols[:30]:
        try:
            # منع تكرار الإشارة لنفس العملة
            if sym in last_signal_time:
                if time.time() - last_signal_time[sym] < CONFIG['cooldown_seconds']:
                    continue
            
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
        except Exception as e:
            print(f"خطأ: {e}")
    print(f"[{datetime.now()}] انتهى الفحص، الانتظار 60 ثانية...")

# ========== متابعة الصفقات ==========
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

# ========== التشغيل الرئيسي ==========
def main():
    send_telegram("✅ *البوت يعمل الآن (فحص كل 60 ثانية)*\nسيتم إرسال إشارات متوسطة الجودة فقط.")
    threading.Thread(target=monitor_trades, daemon=True).start()
    
    # فحص مستمر كل 60 ثانية
    while True:
        continuous_scan()
        time.sleep(60)  # انتظر 60 ثانية بين كل فحص وآخر

if __name__ == "__main__":
    main()