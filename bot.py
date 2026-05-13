#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت سكالبينغ - يعمل كـ Background Worker على Render
"""

import os
import asyncio
import logging
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ========== الإعدادات (ضع التوكن و CHAT_ID مباشرة) ==========
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"

# إعدادات التداول (خفيفة لظهور إشارات سريعة)
CONFIG = {
    "min_volume_usdt": 500_000,
    "min_volume_spike": 1.2,
    "min_score": 40,
    "cooldown_minutes": 5,
    "atr_multiplier_tp1": 1.2,
    "atr_multiplier_tp2": 2.2,
    "atr_multiplier_sl": 1.2,
}

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

# قائمة العملات (أفضل 10 للاختبار)
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT"
]

active_trades = {}
bot = Bot(token=TOKEN)
logging.basicConfig(level=logging.INFO)

async def send_signal(symbol, entry, tp1, tp2, sl, score):
    msg = (
        f"🚀 *إشارة سكالبينغ* 🚀\n\n"
        f"💎 {symbol}\n"
        f"🤖 AI Score: {score}/100\n"
        f"💰 الدخول: {entry:.4f}\n"
        f"🎯 TP1: {tp1:.4f} (+{(tp1/entry-1)*100:.2f}%)\n"
        f"🎯 TP2: {tp2:.4f} (+{(tp2/entry-1)*100:.2f}%)\n"
        f"🛑 SL: {sl:.4f} (-{(1-sl/entry)*100:.2f}%)\n"
        f"⚡️ *إدارة المخاطرة: 1%*"
    )
    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
    active_trades[symbol] = {"entry": entry, "tp1": tp1, "tp2": tp2, "sl": sl, "open_time": datetime.now()}

async def scan_market():
    logging.info("بدء فحص السوق...")
    for sym in SYMBOLS:
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
            await send_signal(sym, entry, tp1, tp2, sl, score)
            await asyncio.sleep(CONFIG['cooldown_minutes'] * 60)
            break
    logging.info("انتهى الفحص.")

async def monitor_trades():
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
                    await bot.send_message(chat_id=CHAT_ID, text=f"🏆 {sym} حقق الهدف الثاني! الربح: {profit*100:.2f}%")
                    del active_trades[sym]
                elif price <= trade['sl'] and not trade.get('closed'):
                    trade['closed'] = True
                    await bot.send_message(chat_id=CHAT_ID, text=f"🛑 {sym} ضرب الستوب! الخسارة: {(trade['entry']-price)/trade['entry']*100:.2f}%")
                    del active_trades[sym]
                elif price >= trade['tp1'] and not trade.get('tp1_hit'):
                    trade['tp1_hit'] = True
                    await bot.send_message(chat_id=CHAT_ID, text=f"🎯 {sym} حقق الهدف الأول (+{profit*100:.2f}%)")
            except Exception as e:
                logging.error(f"خطأ بمتابعة {sym}: {e}")
        await asyncio.sleep(10)

# ========== أوامر التليجرام ==========
async def start(update: Update, ctx):
    await update.message.reply_text("✅ بوت السكالبينغ يعمل. أرسل /scan لفحص يدوي، /test لاختبار الإرسال.")

async def test(update: Update, ctx):
    await update.message.reply_text("🔔 رسالة اختبار: البوت متصل ويعمل بشكل صحيح.")

async def manual_scan(update: Update, ctx):
    await update.message.reply_text("🔄 جاري فحص السوق...")
    await scan_market()

async def status(update: Update, ctx):
    await update.message.reply_text(f"📊 صفقات مفتوحة: {len(active_trades)}")

# ========== التشغيل الرئيسي ==========
async def main():
    # إرسال رسالة فورية فور بدء التشغيل (الأهم)
    await bot.send_message(chat_id=CHAT_ID, text="✅ *البوت يعمل الآن على Render (Background Worker)*\nأرسل /test للتأكد، و /scan لبدء الفحص.", parse_mode='Markdown')
    
    # تشغيل متابعة الصفقات
    asyncio.create_task(monitor_trades())
    
    # بناء تطبيق التليجرام
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("scan", manual_scan))
    app.add_handler(CommandHandler("status", status))
    
    # جدولة فحص تلقائي كل 30 دقيقة
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(lambda _: asyncio.create_task(scan_market()), interval=1800, first=10)
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())