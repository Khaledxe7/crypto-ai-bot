#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت سكالبينغ متكامل – الإصدار النهائي
- أفضل 100 عملة من CoinGecko (بديل مجاني لـ CoinMarketCap)
- رصد أخبار ترامب، إيلون ماسك، الحروب (تايوان، مضيق هرمز)
- متابعة الذهب، الدولار، التضخم، أسعار الفائدة
- مؤشرات فنية (EMA, RSI, ATR) بدون pandas-ta
- إدارة الصفقات وإشعارات الأهداف
- يعمل على Termux و Render 24/7
"""

import os
import re
import json
import time
import asyncio
import logging
import threading
import requests
import feedparser
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from http.server import BaseHTTPRequestHandler, HTTPServer
from deep_translator import GoogleTranslator
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ======================== الإعدادات الأساسية ========================
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
PORT = int(os.getenv("PORT", 10000))

# إعدادات التداول (يمكنك تعديلها كما تشاء)
TRADE_CONFIG = {
    "min_volume_usdt": 2_000_000,      # الحد الأدنى للسيولة اليومية
    "min_volume_spike": 1.5,           # مضاعف الحجم عن المعدل
    "min_score": 85,                   # درجة الذكاء الاصطناعي المطلوبة
    "max_daily_signals": 3,            # الحد الأقصى للإشارات يومياً
    "cooldown_minutes": 30,            # فترة الراحة بين الإشارات
    "max_consecutive_losses": 2,       # أقصى خسائر متتالية
    "atr_multiplier_tp1": 1.2,         # مضاعف ATR للهدف الأول
    "atr_multiplier_tp2": 2.2,         # مضاعف ATR للهدف الثاني
    "atr_multiplier_sl": 1.2,          # مضاعف ATR لوقف الخسارة
    "breakeven_trigger_pct": 0.01,     # تفعيل break-even عند ربح 1%
}

# المتغيرات العامة
TOP_100_SYMBOLS = []          # سيتم تعبئتها تلقائياً
active_trades = {}            # الصفقات المفتوحة
trade_log = []                # سجل الصفقات
macro_cache = {}              # لتخزين بيانات الاقتصاد الكلي
global_alerts = {"trump": [], "musk": [], "war": []}

# إعدادات الترجمة والمشاعر
translator = GoogleTranslator(source='auto', target='ar')
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)

# ======================== 1. جلب أفضل 100 عملة (من CoinGecko مجاناً) ========================
def get_top_100_coins() -> List[str]:
    """جلب أفضل 100 عملة من حيث القيمة السوقية من CoinGecko"""
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            symbols = [item['symbol'].upper() + 'USDT' for item in data if item['symbol'].isalpha()]
            print(f"[✓] تم جلب {len(symbols)} عملة من CoinGecko")
            return symbols
        else:
            print("[!] فشل جلب العملات، استخدم القائمة الاحتياطية")
            return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT"]
    except Exception as e:
        print(f"[!] خطأ في جلب العملات: {e}")
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT"]

def update_coin_list():
    """تحديث قائمة العملات كل 6 ساعات"""
    global TOP_100_SYMBOLS
    TOP_100_SYMBOLS = get_top_100_coins()
    threading.Timer(6 * 3600, update_coin_list).start()

# ======================== 2. المؤشرات الفنية بدون pandas-ta ========================
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
    atr = tr.rolling(window=length).mean()
    return atr

def get_advanced_data(symbol: str, interval: str = '15m', limit: int = 300) -> pd.DataFrame:
    """جلب بيانات Binance وحساب المؤشرات"""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
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
        logging.error(f"خطأ في جلب بيانات {symbol}: {e}")
        return pd.DataFrame()

def multi_timeframe_confirmation(symbol: str) -> bool:
    """تأكيد الاتجاه الصاعد على 1m, 5m, 15m"""
    intervals = ['1m', '5m', '15m']
    bullish = 0
    for tf in intervals:
        df = get_advanced_data(symbol, interval=tf, limit=100)
        if df.empty: continue
        last = df.iloc[-1]
        if last['close'] > last['ema200'] and last['ema20'] > last['ema50']:
            bullish += 1
    return bullish >= 2

# ======================== 3. محرك الاقتصاد الكلي (الذهب، الدولار، التضخم، الفائدة) ========================
def get_macro_data() -> Dict:
    """جلب مؤشر الدولار، سعر الذهب، التضخم، أسعار الفائدة"""
    global macro_cache
    now = datetime.now()
    # تحديث كل ساعة
    if 'last_update' in macro_cache and (now - macro_cache['last_update']).seconds < 3600:
        return macro_cache['data']
    
    result = {}
    try:
        # الدولار (مؤشر DXY)
        dxy = yf.Ticker("DX-Y.NYB")
        dxy_data = dxy.history(period="1d")
        result['dollar_index'] = round(dxy_data['Close'].iloc[-1], 2) if not dxy_data.empty else 98.5
        
        # الذهب
        gold = yf.Ticker("GC=F")
        gold_data = gold.history(period="1d")
        result['gold_price'] = round(gold_data['Close'].iloc[-1], 2) if not gold_data.empty else 2350.0
        
        # التضخم (بيانات ثابتة تقريبية، يمكن استبدالها بـ FRED API)
        result['inflation'] = 3.2  # نسبة مئوية تقريبية
        result['interest_rate'] = 3.5  # سعر الفائدة التقريبي
        
        macro_cache['data'] = result
        macro_cache['last_update'] = now
    except Exception as e:
        logging.error(f"خطأ في جلب البيانات الكلية: {e}")
        result = {'dollar_index': 98.5, 'gold_price': 2350.0, 'inflation': 3.2, 'interest_rate': 3.5}
        macro_cache['data'] = result
        macro_cache['last_update'] = now
    return result

# ======================== 4. رصد الأخبار العالمية (ترامب، ماسك، الحروب) ========================
def scan_global_news():
    """فحص مصادر RSS للأحداث الهامة"""
    try:
        # أخبار ترامب
        trump_feed = feedparser.parse("https://www.reuters.com/technology/us-politics/rss")
        for entry in trump_feed.entries[:5]:
            if 'trump' in entry.title.lower():
                global_alerts['trump'].append(entry.title)
        # أخبار إيلون ماسك
        musk_feed = feedparser.parse("https://www.independent.co.uk/topic/elon-musk.rss")
        for entry in musk_feed.entries[:5]:
            if 'musk' in entry.title.lower() or 'elon' in entry.title.lower():
                global_alerts['musk'].append(entry.title)
        # أخبار الحروب (تايوان، مضيق هرمز، الصين، إيران)
        war_keywords = ['taiwan', 'strait of hormuz', 'china taiwan', 'iran', 'hormuz', 'war', 'conflict']
        war_feed = feedparser.parse("https://www.reuters.com/world/rss")
        for entry in war_feed.entries[:10]:
            title = entry.title.lower()
            if any(kw in title for kw in war_keywords):
                global_alerts['war'].append(title)
    except Exception as e:
        logging.error(f"خطأ في فحص الأخبار: {e}")
    # إعادة الجدولة كل 20 دقيقة
    threading.Timer(20 * 60, scan_global_news).start()

# ======================== 5. حساب درجة الذكاء الاصطناعي للعملة ========================
def calculate_ai_score(df: pd.DataFrame, macro: Dict) -> int:
    """حساب درجة من 0-100 بناءً على المؤشرات الفنية والاقتصاد الكلي"""
    if df.empty:
        return 0
    last = df.iloc[-1]
    score = 0
    
    # الاتجاه العام (Trend) – 25 نقطة
    if last['close'] > last['ema200']:
        score += 15
    if last['ema20'] > last['ema50']:
        score += 10
    
    # الزخم (RSI) – 15 نقطة
    if 55 < last['rsi'] < 75:
        score += 15
    elif last['rsi'] > 75:
        score += 5
    
    # الحجم (Volume) – 20 نقطة
    vol_ratio = last['vol'] / last['vol_sma'] if last['vol_sma'] != 0 else 1
    if vol_ratio > TRADE_CONFIG['min_volume_spike']:
        score += 20
    elif vol_ratio > 1.2:
        score += 10
    
    # السيولة – 10 نقاط
    if last['vol'] * last['close'] > TRADE_CONFIG['min_volume_usdt']:
        score += 10
    
    # التقلب (ATR) – 10 نقاط
    atr_pct = (last['atr'] / last['close']) * 100
    if 0.5 <= atr_pct <= 3:
        score += 10
    
    # تصحيح حسب الاقتصاد الكلي – 20 نقطة (قد تكون سالبة)
    if macro['dollar_index'] > 100:
        score -= 10
    if macro['inflation'] > 4:
        score -= 10
    if macro['interest_rate'] > 4.5:
        score -= 5
    
    return max(0, min(100, score))

# ======================== 6. إدارة المخاطر اليومية ========================
class RiskManager:
    def __init__(self):
        self.reset_daily()
    
    def reset_daily(self):
        self.daily_signals = 0
        self.loss_streak = 0
        self.last_day = datetime.now().day
    
    def can_send_signal(self) -> bool:
        now = datetime.now()
        if now.day != self.last_day:
            self.reset_daily()
        return (self.daily_signals < TRADE_CONFIG['max_daily_signals'] and
                self.loss_streak < TRADE_CONFIG['max_consecutive_losses'])
    
    def record_signal(self):
        self.daily_signals += 1
        self.last_signal_time = datetime.now()
    
    def record_win(self):
        self.loss_streak = 0
    
    def record_loss(self):
        self.loss_streak += 1

risk_manager = RiskManager()

# ======================== 7. إرسال الإشارات ========================
async def send_signal(symbol: str, entry: float, tp1: float, tp2: float, sl: float, score: int, macro: Dict, news_summary: str = ""):
    """تنسيق وإرسال إشارة التداول إلى تليجرام"""
    message = (
        f"🚀 *إشارة سكالبينغ عالية الجودة* 🚀\n\n"
        f"💎 العملة: `{symbol}`\n"
        f"🤖 درجة AI: {score}/100\n"
        f"💰 سعر الدخول: {entry:.6f}\n"
        f"🎯 الهدف الأول: {tp1:.6f} (+{(tp1/entry-1)*100:.2f}%)\n"
        f"🎯 الهدف الثاني: {tp2:.6f} (+{(tp2/entry-1)*100:.2f}%)\n"
        f"🛑 وقف الخسارة: {sl:.6f} (-{(1-sl/entry)*100:.2f}%)\n\n"
        f"📊 *البيئة الاقتصادية:*\n"
        f"💵 مؤشر الدولار: {macro['dollar_index']}\n"
        f"🥇 سعر الذهب: ${macro['gold_price']}\n"
        f"📈 التضخم: {macro['inflation']}% | سعر الفائدة: {macro['interest_rate']}%\n\n"
        f"📰 *أخبار عاجلة:*\n{news_summary if news_summary else 'لا توجد أخبار مؤثرة حالياً'}\n\n"
        f"⚠️ *إدارة المخاطرة: 1% من رأس المال*"
    )
    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
    risk_manager.record_signal()
    active_trades[symbol] = {
        'entry': entry, 'tp1': tp1, 'tp2': tp2, 'sl': sl,
        'open_time': datetime.now(), 'breakeven': False, 'tp1_hit': False, 'closed': False
    }

# ======================== 8. متابعة الصفقات المفتوحة ========================
async def monitor_trades():
    """مراقبة الأسعار وإرسال الإشعارات عند تحقيق الأهداف أو ضرب الستوب"""
    while True:
        for symbol, trade in list(active_trades.items()):
            try:
                df = get_advanced_data(symbol, interval='1m', limit=5)
                if df.empty:
                    continue
                current = df['close'].iloc[-1]
                profit_pct = (current - trade['entry']) / trade['entry']
                
                # تفعيل Break-even عند ربح 1%
                if profit_pct >= TRADE_CONFIG['breakeven_trigger_pct'] and not trade.get('breakeven'):
                    trade['sl'] = trade['entry']
                    trade['breakeven'] = True
                    await bot.send_message(chat_id=CHAT_ID, text=f"🛡️ *{symbol}*: تم نقل وقف الخسارة إلى نقطة الدخول (Break-even)")
                
                # تحقيق الهدف الأول
                if current >= trade['tp1'] and not trade.get('tp1_hit'):
                    trade['tp1_hit'] = True
                    duration = datetime.now() - trade['open_time']
                    await bot.send_message(chat_id=CHAT_ID, text=f"🎯 *تحقق الهدف الأول لـ {symbol}* 🎯\nالربح: {profit_pct*100:.2f}%\nالوقت: {duration.seconds//60} دقيقة")
                
                # تحقيق الهدف الثاني (إغلاق الصفقة)
                if current >= trade['tp2'] and not trade.get('closed'):
                    trade['closed'] = True
                    duration = datetime.now() - trade['open_time']
                    await bot.send_message(chat_id=CHAT_ID, text=f"🏆 *تم إغلاق صفقة {symbol} بتحقيق الهدف الثاني* 🏆\nإجمالي الربح: {profit_pct*100:.2f}%\nالوقت: {duration.seconds//60} دقيقة")
                    risk_manager.record_win()
                    del active_trades[symbol]
                
                # ضرب وقف الخسارة
                if current <= trade['sl'] and not trade.get('closed'):
                    trade['closed'] = True
                    loss_pct = (trade['entry'] - current) / trade['entry'] * 100
                    await bot.send_message(chat_id=CHAT_ID, text=f"🛑 *تم ضرب وقف الخسارة لـ {symbol}* 🛑\nالخسارة: {loss_pct:.2f}%\nتم إغلاق الصفقة.")
                    risk_manager.record_loss()
                    del active_trades[symbol]
            except Exception as e:
                logging.error(f"خطأ في متابعة {symbol}: {e}")
        await asyncio.sleep(10)

# ======================== 9. المحرك الرئيسي للمسح وإرسال الإشارات ========================
async def scan_and_signal():
    """مسح السوق وتحليل العملات وإرسال الإشارات"""
    logging.info("بدء دورة المسح...")
    macro = get_macro_data()
    
    # إعداد ملخص الأخبار العاجلة
    news_summary = ""
    if global_alerts['trump']:
        news_summary += f"🇺🇸 ترامب: {global_alerts['trump'][-1][:50]}...\n"
    if global_alerts['musk']:
        news_summary += f"🚀 إيلون ماسك: {global_alerts['musk'][-1][:50]}...\n"
    if global_alerts['war']:
        news_summary += f"⚔️ توتر جيوسياسي: {global_alerts['war'][-1][:50]}...\n"
    
    # إرسال تقرير السوق كل 6 ساعات
    if datetime.now().hour % 6 == 0 and datetime.now().minute < 10:
        await bot.send_message(chat_id=CHAT_ID, text=f"📊 *تقرير السوق*\n💵 الدولار: {macro['dollar_index']}\n🥇 الذهب: ${macro['gold_price']}\n📈 التضخم: {macro['inflation']}%\n📉 سعر الفائدة: {macro['interest_rate']}%\n{news_summary}")
    
    # فحص أول 30 عملة من القائمة (لتوفير الوقت)
    for symbol in TOP_100_SYMBOLS[:30]:
        if not risk_manager.can_send_signal():
            logging.info("تم الوصول للحد اليومي أو الخسائر المتتالية، إيقاف المسح.")
            break
        df = get_advanced_data(symbol)
        if df.empty:
            continue
        score = calculate_ai_score(df, macro)
        if score < TRADE_CONFIG['min_score']:
            continue
        # تأكيد إضافي
        last = df.iloc[-1]
        if last['vol'] * last['close'] < TRADE_CONFIG['min_volume_usdt']:
            continue
        if last['vol'] / last['vol_sma'] < TRADE_CONFIG['min_volume_spike']:
            continue
        if not multi_timeframe_confirmation(symbol):
            continue
        
        # حساب الأهداف الديناميكية
        entry = last['close']
        atr = last['atr']
        tp1 = entry + (atr * TRADE_CONFIG['atr_multiplier_tp1'])
        tp2 = entry + (atr * TRADE_CONFIG['atr_multiplier_tp2'])
        sl = entry - (atr * TRADE_CONFIG['atr_multiplier_sl'])
        
        # إرسال الإشارة
        await send_signal(symbol, entry, tp1, tp2, sl, score, macro, news_summary)
        await asyncio.sleep(TRADE_CONFIG['cooldown_minutes'] * 60)
    
    logging.info("انتهت دورة المسح.")

# ======================== 10. أوامر البوت على تليجرام ========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *بوت السكالبينغ المتكامل*\n\n"
        "✅ يعمل 24/7 مع تحليل أفضل 100 عملة\n"
        "📊 متابعة الذهب، الدولار، التضخم، أسعار الفائدة\n"
        "🌍 رصد أخبار ترامب، ماسك، والأزمات العالمية\n"
        "🎯 إشارات سكالبينغ عالية الجودة فقط\n\n"
        "الأوامر المتاحة:\n"
        "/scan – مسح فوري للسوق\n"
        "/status – عرض حالة البوت والصفقات\n"
        "/news – عرض آخر الأخبار العاجلة\n"
        "/help – هذه الرسالة",
        parse_mode='Markdown'
    )

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 جاري مسح السوق وإرسال الإشارات المناسبة...")
    await scan_and_signal()

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active = len(active_trades)
    msg = (
        f"📈 *حالة البوت*\n"
        f"إشارات اليوم: {risk_manager.daily_signals}/{TRADE_CONFIG['max_daily_signals']}\n"
        f"خسائر متتالية: {risk_manager.loss_streak}/{TRADE_CONFIG['max_consecutive_losses']}\n"
        f"صفقات مفتوحة: {active}\n"
        f"آخر تحديث للعملات: {len(TOP_100_SYMBOLS)} عملة"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    news_text = "📰 *آخر الأخبار العاجلة:*\n\n"
    if global_alerts['trump']:
        news_text += f"🇺🇸 *ترامب:* {global_alerts['trump'][-1][:100]}...\n"
    if global_alerts['musk']:
        news_text += f"🚀 *إيلون ماسك:* {global_alerts['musk'][-1][:100]}...\n"
    if global_alerts['war']:
        news_text += f"⚔️ *أزمات جيوسياسية:* {global_alerts['war'][-1][:100]}...\n"
    if not any(global_alerts.values()):
        news_text += "لا توجد أخبار جديدة مؤثرة حالياً."
    await update.message.reply_text(news_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_command(update, context)

# ======================== 11. خادم الصحة لـ Render ========================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running 24/7")
def run_health_server():
    server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
    server.serve_forever()

# ======================== 12. التشغيل الرئيسي ========================
async def main():
    # بدء خادم الصحة
    threading.Thread(target=run_health_server, daemon=True).start()
    
    # بدء متابعة الصفقات
    asyncio.create_task(monitor_trades())
    
    # بدء تحديث قائمة العملات وفحص الأخبار
    update_coin_list()
    scan_global_news()
    
    # بناء تطبيق تليجرام
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("scan", scan_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # جدولة المسح التلقائي كل 30 دقيقة
    job_queue = app.job_queue
    job_queue.run_repeating(lambda _: asyncio.create_task(scan_and_signal()), interval=1800, first=10)
    
    # إرسال رسالة بدء التشغيل
    await bot.send_message(chat_id=CHAT_ID, text="✅ *البوت يعمل الآن بنجاح*\n\nتم تفعيل المسح التلقائي كل 30 دقيقة، وسيتم إرسال الإشارات عند توفرها.", parse_mode='Markdown')
    
    # بدء البوت
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())