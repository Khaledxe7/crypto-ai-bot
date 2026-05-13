#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت سكالبينغ متكامل - بدون pandas-ta (يعمل على Termux و أي خادم)
"""

import os
import threading
import asyncio
import requests
import pandas as pd
import numpy as np
import feedparser
import yfinance as yf
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from deep_translator import GoogleTranslator
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ========== الإعدادات الأساسية ==========
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
PORT = int(os.getenv("PORT", 10000))

TOP_100_SYMBOLS = []  # سيتم تعبئتها لاحقاً
active_trades = {}

TRADE_CONFIG = {
    "min_volume_usdt": 2_000_000,
    "min_volume_spike": 1.5,
    "min_score": 85,
    "max_daily_signals": 3,
    "cooldown_minutes": 30,
    "max_consecutive_losses": 2,
    "atr_multiplier_tp1": 1.2,
    "atr_multiplier_tp2": 2.2,
    "atr_multiplier_sl": 1.2,
}

bot = Bot(token=TOKEN)
translator = GoogleTranslator(source='en', target='ar')

# ========== حساب المؤشرات يدوياً ==========
def compute_ema(series, length):
    """EMA يدوي"""
    return series.ewm(span=length, adjust=False).mean()

def compute_rsi(series, length=14):
    """RSI يدوي"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=length, min_periods=length).mean()
    avg_loss = loss.rolling(window=length, min_periods=length).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def compute_atr(high, low, close, length=14):
    """ATR يدوي"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=length).mean()
    return atr

# ========== جلب بيانات Binance مع المؤشرات ==========
def get_advanced_data(symbol, interval='15m', limit=300):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    data = requests.get(url, timeout=15).json()
    df = pd.DataFrame(data, columns=['time','open','high','low','close','vol','c_time','q_v','tr','tb','tq','i'])
    df = df.astype(float)
    df['ema20'] = compute_ema(df['close'], 20)
    df['ema50'] = compute_ema(df['close'], 50)
    df['ema200'] = compute_ema(df['close'], 200)
    df['rsi'] = compute_rsi(df['close'], 14)
    df['atr'] = compute_atr(df['high'], df['low'], df['close'], 14)
    df['vol_sma'] = df['vol'].rolling(window=20).mean()
    return df

# ========== أفضل 100 عملة من CoinMarketCap (محاكاة) ==========
def get_top_100_coins():
    try:
        # ملاحظة: هذا الرابط التجريبي لا يحتاج مفتاحاً (بيانات وهمية للتوضيح)
        # للاستخدام الحقيقي احصل على مفتاح مجاني من CoinMarketCap
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false"
        data = requests.get(url, timeout=15).json()
        symbols = [item['symbol'].upper() + 'USDT' for item in data]
        return symbols
    except:
        return ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT","DOTUSDT","LINKUSDT"]

def update_coin_list():
    global TOP_100_SYMBOLS
    new_list = get_top_100_coins()
    if new_list:
        TOP_100_SYMBOLS = new_list
    threading.Timer(3600*6, update_coin_list).start()

# ========== المتغيرات الكلية ==========
def get_macro():
    try:
        dxy = yf.Ticker("DX-Y.NYB")
        dxy_data = dxy.history(period="1d")
        dollar_index = round(dxy_data['Close'].iloc[-1], 2) if not dxy_data.empty else 98.5
        
        gold = yf.Ticker("GC=F")
        gold_data = gold.history(period="1d")
        gold_price = round(gold_data['Close'].iloc[-1], 2) if not gold_data.empty else 2350.0
        return {"dollar_index": dollar_index, "gold_price": gold_price}
    except:
        return {"dollar_index": 98.5, "gold_price": 2350.0}

# ========== الأخبار العالمية ==========
global_alerts = {"trump": [], "musk": [], "war": []}
def scan_news():
    try:
        feeds = {
            "trump": "https://www.reuters.com/technology/us-politics/rss",
            "musk": "https://www.independent.co.uk/topic/elon-musk.rss",
            "war": "https://www.reuters.com/world/rss"
        }
        for key, url in feeds.items():
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                title = entry.title.lower()
                if key == "trump" and "trump" in title:
                    global_alerts["trump"].append(title)
                elif key == "musk" and ("musk" in title or "elon" in title):
                    global_alerts["musk"].append(title)
                elif key == "war" and any(w in title for w in ["taiwan","hormuz","china","iran","war"]):
                    global_alerts["war"].append(title)
    except:
        pass
    threading.Timer(20*60, scan_news).start()

# ========== حساب درجة الصفقة ==========
def calculate_score(df, macro):
    if df.empty:
        return 0
    last = df.iloc[-1]
    score = 0
    if last['close'] > last['ema200']: score += 25
    if last['ema20'] > last['ema50']: score += 15
    if 55 < last['rsi'] < 75: score += 15
    vol_ratio = last['vol'] / last['vol_sma'] if last['vol_sma'] != 0 else 1
    if vol_ratio > TRADE_CONFIG["min_volume_spike"]: score += 20
    if last['vol'] * last['close'] > TRADE_CONFIG["min_volume_usdt"]: score += 10
    if macro['dollar_index'] > 100: score -= 10
    return max(0, min(100, score))

# ========== إدارة المخاطر ==========
class RiskManager:
    def __init__(self):
        self.daily_signals = 0
        self.loss_streak = 0
        self.last_day = datetime.now().day
    def can_send(self):
        if datetime.now().day != self.last_day:
            self.daily_signals = 0
            self.loss_streak = 0
            self.last_day = datetime.now().day
        return self.daily_signals < TRADE_CONFIG["max_daily_signals"] and self.loss_streak < TRADE_CONFIG["max_consecutive_losses"]
    def record_signal(self): self.daily_signals += 1
    def record_loss(self): self.loss_streak += 1
    def record_win(self): self.loss_streak = 0

risk = RiskManager()

# ========== إرسال الإشارة ==========
async def send_signal(symbol, entry, tp1, tp2, sl, score, macro):
    msg = (
        f"🚀 *إشارة سكالبينغ*\n"
        f"💎 {symbol}\n"
        f"🤖 AI Score: {score}/100\n"
        f"💰 الدخول: {entry:.6f}\n"
        f"🎯 TP1: {tp1:.6f}\n"
        f"🎯 TP2: {tp2:.6f}\n"
        f"🛑 SL: {sl:.6f}\n"
        f"💵 الدولار: {macro['dollar_index']}\n"
        f"🥇 الذهب: ${macro['gold_price']}"
    )
    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
    risk.record_signal()
    active_trades[symbol] = {"entry": entry, "tp1": tp1, "tp2": tp2, "sl": sl, "open_time": datetime.now()}

# ========== متابعة الصفقات ==========
async def monitor_trades():
    while True:
        for sym, trade in list(active_trades.items()):
            try:
                df = get_advanced_data(sym, '1m')
                if df.empty: continue
                price = df['close'].iloc[-1]
                profit = (price - trade['entry']) / trade['entry']
                if price >= trade['tp1'] and not trade.get('tp1_hit'):
                    trade['tp1_hit'] = True
                    await bot.send_message(chat_id=CHAT_ID, text=f"🎯 TP1 hit for {sym} (+{profit*100:.2f}%)")
                if price >= trade['tp2'] and not trade.get('closed'):
                    trade['closed'] = True
                    await bot.send_message(chat_id=CHAT_ID, text=f"🏆 {sym} closed TP2! Profit: {profit*100:.2f}%")
                    risk.record_win()
                    del active_trades[sym]
                if price <= trade['sl'] and not trade.get('closed'):
                    trade['closed'] = True
                    loss = (trade['entry'] - price)/trade['entry']*100
                    await bot.send_message(chat_id=CHAT_ID, text=f"🛑 {sym} hit SL! Loss: {loss:.2f}%")
                    risk.record_loss()
                    del active_trades[sym]
            except:
                pass
        await asyncio.sleep(10)

# ========== محرك التداول ==========
async def trading_engine():
    macro = get_macro()
    for symbol in TOP_100_SYMBOLS[:30]:
        df = get_advanced_data(symbol)
        if df.empty: continue
        score = calculate_score(df, macro)
        if score >= TRADE_CONFIG["min_score"] and risk.can_send():
            last = df.iloc[-1]
            entry = last['close']
            atr = last['atr']
            tp1 = entry + atr * TRADE_CONFIG["atr_multiplier_tp1"]
            tp2 = entry + atr * TRADE_CONFIG["atr_multiplier_tp2"]
            sl = entry - atr * TRADE_CONFIG["atr_multiplier_sl"]
            await send_signal(symbol, entry, tp1, tp2, sl, score, macro)
            await asyncio.sleep(TRADE_CONFIG["cooldown_minutes"] * 60)

async def scan(update: Update, ctx):
    await update.message.reply_text("جاري المسح...")
    await trading_engine()

async def start(update: Update, ctx):
    await update.message.reply_text("بوت السكالبينغ يعمل الآن ✅")

async def status(update: Update, ctx):
    await update.message.reply_text(f"إشارات اليوم: {risk.daily_signals} | خسائر متتالية: {risk.loss_streak} | صفقات مفتوحة: {len(active_trades)}")

# ========== خادم الصحة ==========
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")
def run_health():
    server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
    server.serve_forever()

# ========== التشغيل الرئيسي ==========
async def main():
    threading.Thread(target=run_health, daemon=True).start()
    asyncio.create_task(monitor_trades())
    update_coin_list()
    scan_news()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("status", status))
    await bot.send_message(chat_id=CHAT_ID, text="✅ البوت يعمل (نسخة بدون numba)")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())