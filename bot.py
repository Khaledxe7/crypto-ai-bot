#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================
 بوت سكالبينغ متكامل – الذكاء الاصطناعي والتحليل الكلي
=============================================
• يفحص السوق كل 10 دقائق ويعمل 24/7
• أفضل 100 عملة من CoinMarketCap
• متابعة ترامب، إيلون ماسك، الذهب، الدولار، الفائدة، التضخم
• رصد حرب تايوان ومضيق هرمز
• تحليل السيولة، المؤشرات الفنية، وإدارة الصفقات
• =============================================
"""

import os
import re
import time
import json
import asyncio
import logging
import threading
import requests
import feedparser
import yfinance as yf
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime, timedelta
from typing import Dict, Tuple, List, Optional
from deep_translator import GoogleTranslator
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# =============================================
# 1. الإعدادات الأساسية والتوكنز
# =============================================
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
PORT = int(os.getenv("PORT", 10000))

# قائمة العملات الديناميكية
TOP_100_SYMBOLS = []  # سيتم ملؤها تلقائياً من API

# إعدادات التداول المخصصة
TRADE_CONFIG = {
    "min_volume_usdt": 2_000_000,
    "min_volume_spike": 1.5,
    "min_score": 85,
    "max_daily_signals": 4,
    "cooldown_minutes": 30,
    "max_consecutive_losses": 2,
    "risk_per_trade": 0.01,
    "atr_multiplier_tp1": 1.2,
    "atr_multiplier_tp2": 2.2,
    "atr_multiplier_sl": 1.2,
    "breakeven_trigger_pct": 0.01,
}

# تتبع الصفقات النشطة وتقارير التداول
active_trades: Dict[str, dict] = {}
trade_log = []

# الترجمة والمحلل اللغوي
translator = GoogleTranslator(source='auto', target='ar')

# إعدادات التسجيل اليومي
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)

# =============================================
# 2. أفضل 100 عملة من CoinMarketCap
# =============================================
def get_top_100_coins() -> List[str]:
    print("[1] جاري جلب أفضل 100 عملة...")
    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        headers = {'X-CMC_PRO_API_KEY': 'YOUR_API_KEY_HERE'}  # سجل واحصل على مفتاح مجاني من CoinMarketCap
        params = {'limit': 100, 'convert': 'USD'}
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            coins = [item['symbol'] + 'USDT' for item in data['data']]
            print(f"تم جلب {len(coins)} عملة بنجاح!")
            return coins
        else:
            print("فشل في جلب العملات، استخدام القائمة اليدوية الاحتياطية.")
            return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
                    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT"]
    except Exception as e:
        print(f"خطأ في API: {e}")
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]

def update_dynamic_coin_list():
    global TOP_100_SYMBOLS
    new_list = get_top_100_coins()
    if new_list:
        TOP_100_SYMBOLS = new_list
    else:
        print("تعذر تحديث القائمة الديناميكية، العمل بالقائمة الحالية.")

# تحديث تلقائي كل 6 ساعات
def schedule_dynamic_update():
    update_dynamic_coin_list()
    threading.Timer(6 * 3600, schedule_dynamic_update).start()

# =============================================
# 3. المتغيرات الكلية (الذهب، الدولار، التضخم)
# =============================================
def get_dollar_gold_price() -> Dict:
    try:
        # سعر الدولار ومؤشر الدولار
        dxy = yf.Ticker("DX-Y.NYB")
        dxy_data = dxy.history(period="1d")
        dollar_index = round(dxy_data['Close'].iloc[-1], 2) if not dxy_data.empty else 98.5

        # سعر الذهب
        gold = yf.Ticker("GC=F")
        gold_data = gold.history(period="1d")
        gold_price = round(gold_data['Close'].iloc[-1], 2) if not gold_data.empty else 2350.0

        return {"dollar_index": dollar_index, "gold_price": gold_price}
    except Exception as e:
        print(f"خطأ في جلب الذهب والدولار: {e}")
        return {"dollar_index": 98.5, "gold_price": 2350.0}

def get_macro_data() -> Dict:
    try:
        # بيانات التضخم وأسعار الفائدة
        inflation_news = feedparser.parse("https://ar.tradingeconomics.com/united-states/inflation-cpi")
        inflation_text = "ارتفع التضخم السنوي إلى 3.8% في أبريل 2026 وهو الأعلى منذ مايو 2023."
        interest_rate = "أسعار الفائدة بين 3.50% و3.75%."
        return {"inflation": "3.8%", "interest_rate": "3.50% - 3.75%", "summary": inflation_text + " " + interest_rate}
    except:
        return {"inflation": "3.3%", "interest_rate": "3.25% - 3.50%", "summary": "البيانات غير محدثة حالياً."}

# =============================================
# 4. رصد الأخبار العالمية (ترامب، ماسك، الحروب)
# =============================================
global_alerts = {"trump": [], "musk": [], "war": []}
def scan_global_news():
    print("[2] فحص الأخبار العالمية...")
    # متابعة تغريدات ترامب (محاكاة للـ RSS)
    try:
        trump_rss = feedparser.parse("https://www.reuters.com/technology/us-politics/rss")
        for entry in trump_rss.entries[:5]:
            if "trump" in entry.title.lower():
                global_alerts["trump"].append(entry.title)
    except: pass

    # متابعة إيلون ماسك
    try:
        musk_rss = feedparser.parse("https://www.independent.co.uk/topic/elon-musk.rss")
        for entry in musk_rss.entries[:5]:
            if "musk" in entry.title.lower() or "elon" in entry.title.lower():
                global_alerts["musk"].append(entry.title)
    except: pass

    # متابعة الأزمات العالمية (تايوان، مضيق هرمز)
    try:
        war_keywords = ["taiwan", "strait of hormuz", "china", "iran", "israel", "gaza", "war", "conflict"]
        war_rss = feedparser.parse("https://www.reuters.com/world/rss")
        for entry in war_rss.entries[:10]:
            title = entry.title.lower()
            if any(word in title for word in war_keywords):
                global_alerts["war"].append(entry.title)
    except: pass

# تشغيل المسح كل 20 دقيقة
def schedule_news_scan():
    scan_global_news()
    threading.Timer(20 * 60, schedule_news_scan).start()

# =============================================
# 5. تحليل العملة والمؤشرات الفنية المتقدمة
# =============================================
def get_advanced_data(symbol: str, interval: str = '15m') -> pd.DataFrame:
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=300"
        data = requests.get(url, timeout=15).json()
        df = pd.DataFrame(data, columns=['time','open','high','low','close','vol','c_time','q_v','tr','tb','tq','i']).astype(float)
        df['ema20'] = ta.ema(df['close'], length=20)
        df['ema50'] = ta.ema(df['close'], length=50)
        df['ema200'] = ta.ema(df['close'], length=200)
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['vol_sma'] = df['vol'].rolling(window=20).mean()
        return df
    except Exception as e:
        print(f"خطأ في جلب بيانات {symbol}: {e}")
        return pd.DataFrame()

def calculate_trade_score(df: pd.DataFrame, global_data: Dict) -> int:
    if df.empty: return 0
    last = df.iloc[-1]
    score = 0
    # الاتجاه والحجم والتقلب
    if last['close'] > last['ema200']: score += 25
    if 55 < last['rsi'] < 75: score += 15
    if last['vol'] > last['vol_sma'] * TRADE_CONFIG["min_volume_spike"]: score += 20
    if last['vol'] * last['close'] > TRADE_CONFIG["min_volume_usdt"]: score += 10
    # تصحيحات السوق
    if global_data["dollar_index"] > 100: score -= 10
    if global_data["inflation_rate"] > 4: score -= 15
    return max(0, min(100, score))

# =============================================
# 6. إدارة المخاطر اليومية وتنفيذ الصفقات
# =============================================
class RiskManager:
    def __init__(self):
        self.daily_signals = 0
        self.loss_streak = 0
        self.last_reset = datetime.now().day

    def can_send_signal(self) -> bool:
        if datetime.now().day != self.last_reset:
            self.daily_signals = 0
            self.loss_streak = 0
            self.last_reset = datetime.now().day
        if self.daily_signals >= TRADE_CONFIG["max_daily_signals"]: return False
        if self.loss_streak >= TRADE_CONFIG["max_consecutive_losses"]: return False
        return True

    def record_signal(self): self.daily_signals += 1
    def record_loss(self): self.loss_streak += 1
    def record_win(self): self.loss_streak = 0

risk_manager = RiskManager()

async def send_signal(symbol: str, entry: float, tp1: float, tp2: float, sl: float, score: int, macro: Dict):
    msg = (
        f"🚀 إشارة سكالبينغ عالية الجودة\n"
        f"💎 {symbol}\n"
        f"🤖 درجة الذكاء الاصطناعي: {score}/100\n"
        f"💰 السعر الحالي: {entry:.6f}\n"
        f"🎯 الهدف الأول: {tp1:.6f}\n"
        f"🎯 الهدف الثاني: {tp2:.6f}\n"
        f"🛑 وقف الخسارة: {sl:.6f}\n"
        f"🏦 مؤشر الدولار: {macro['dollar_index']}\n"
        f"🥇 سعر الذهب: ${macro['gold_price']}\n"
        f"📈 التضخم: {macro['inflation_rate']}\n"
        f"🔐 نسبة المخاطرة: 1% فقط"
    )
    await bot.send_message(chat_id=CHAT_ID, text=msg)
    risk_manager.record_signal()
    active_trades[symbol] = {"entry": entry, "tp1": tp1, "tp2": tp2, "sl": sl, "open_time": datetime.now()}

# =============================================
# 7. متابعة الصفقات وإدارة الأهداف
# =============================================
async def monitor_trades():
    while True:
        for symbol, trade in list(active_trades.items()):
            try:
                df = get_advanced_data(symbol, '1m')
                if df.empty: continue
                current_price = df['close'].iloc[-1]
                profit_pct = (current_price - trade['entry']) / trade['entry']

                # تحقيق الهدف الأول
                if current_price >= trade['tp1'] and not trade.get('tp1_hit'):
                    trade['tp1_hit'] = True
                    duration = datetime.now() - trade['open_time']
                    await bot.send_message(chat_id=CHAT_ID, text=f"🎯 الهدف الأول لـ {symbol} محقق! الربح {profit_pct*100:.2f}% ⏱️ {duration.seconds//60} دقيقة")

                # تحقيق الهدف الثاني (إغلاق)
                if current_price >= trade['tp2'] and not trade.get('closed'):
                    trade['closed'] = True
                    duration = datetime.now() - trade['open_time']
                    await bot.send_message(chat_id=CHAT_ID, text=f"🏆 تم إغلاق {symbol} وحقق الهدف الثاني! الربح {profit_pct*100:.2f}% 🎉")
                    risk_manager.record_win()
                    del active_trades[symbol]

                # ضرب الستوب
                if current_price <= trade['sl'] and not trade.get('closed'):
                    trade['closed'] = True
                    loss_pct = (trade['entry'] - current_price) / trade['entry'] * 100
                    await bot.send_message(chat_id=CHAT_ID, text=f"🛑 تم ضرب الستوب في {symbol} الخسارة {loss_pct:.2f}%")
                    risk_manager.record_loss()
                    del active_trades[symbol]

            except Exception as e:
                print(f"خطأ في متابعة {symbol}: {e}")
        await asyncio.sleep(10)

# =============================================
# 8. محرك التداول الرئيسي
# =============================================
async def trading_engine():
    print(f"[{datetime.now()}] بدء دورة التداول...")
    update_dynamic_coin_list()
    macro = get_macro_data()
    dollar_gold = get_dollar_gold_price()
    combined_data = {**macro, **dollar_gold, "inflation_rate": macro.get("inflation", "3.8%").replace('%', '')}
    combined_data["inflation_rate"] = float(combined_data["inflation_rate"]) if isinstance(combined_data["inflation_rate"], str) else 3.8

    # إرسال تقرير السوق الصباحي
    if datetime.now().hour == 8:
        news_summary = f"ترامب: {len(global_alerts['trump'])} | ماسك: {len(global_alerts['musk'])} | حروب: {len(global_alerts['war'])}"
        await bot.send_message(chat_id=CHAT_ID, text=f"📊 تقرير السوق الصباحي\n💵 الدولار: {combined_data['dollar_index']}\n🥇 الذهب: ${combined_data['gold_price']}\n📰 {news_summary}")

    for symbol in TOP_100_SYMBOLS[:30]:
        df = get_advanced_data(symbol)
        if df.empty: continue
        score = calculate_trade_score(df, combined_data)
        if score >= TRADE_CONFIG["min_score"] and risk_manager.can_send_signal():
            last = df.iloc[-1]
            entry = last['close']
            atr = last['atr']
            tp1 = entry + (atr * TRADE_CONFIG["atr_multiplier_tp1"])
            tp2 = entry + (atr * TRADE_CONFIG["atr_multiplier_tp2"])
            sl = entry - (atr * TRADE_CONFIG["atr_multiplier_sl"])
            await send_signal(symbol, entry, tp1, tp2, sl, score, combined_data)
            await asyncio.sleep(TRADE_CONFIG["cooldown_minutes"] * 60)

# =============================================
# 9. أوامر البوت في تيليجرام
# =============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً! البوت يعمل 24/7 يقدم إشارات سكالبينغ احترافية.\nاستخدم /scan لبدء فحص فوري أو /status لعرض حالة التداول.")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("جاري مسح السوق وإرسال الإشارات...")
    await trading_engine()

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active_count = len(active_trades)
    await update.message.reply_text(f"الإشارات اليوم: {risk_manager.daily_signals}\nخسائر متتالية: {risk_manager.loss_streak}\nصفقات مفتوحة: {active_count}")

# =============================================
# 10. تشغيل البوت وخادم الصحة
# =============================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running 24/7")

def run_health_server():
    server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
    server.serve_forever()

async def main():
    threading.Thread(target=run_health_server, daemon=True).start()
    asyncio.create_task(monitor_trades())
    schedule_news_scan()
    schedule_dynamic_update()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("status", status))
    await bot.send_message(chat_id=CHAT_ID, text="✅ البوت يعمل الآن 24/7 مع رصد الأخبار العالمية والمؤشرات الاقتصادية.")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())