import requests
import asyncio
import math
from telegram import Bot
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# --- إعدادات البوت ---
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
bot = Bot(token=TOKEN)

last_prices = {}
active_trades = {}

# خادم وهمي لـ Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Free and Alive")

def run_health_server():
    server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
    server.serve_forever()

def get_targets(price):
    return {
        "target": price * 1.03, # ربح 3%
        "stop": price * 0.98    # خسارة 2%
    }

async def monitor_trades():
    global active_trades
    if not active_trades: return
    try:
        res = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=5).json()
        prices = {item['symbol']: float(item['price']) for item in res if item['symbol'].endswith('USDT')}
        for symbol, trade in list(active_trades.items()):
            if symbol in prices:
                cp = prices[symbol]
                if cp >= trade['target']:
                    await bot.send_message(CHAT_ID, f"💰 **تم ضرب الهدف (+3%)**\n✅ #{symbol.replace('USDT','')}\nسعر الخروج: {cp:,.4f}")
                    del active_trades[symbol]
                elif cp <= trade['stop']:
                    await bot.send_message(CHAT_ID, f"🛑 **خرجنا ستوب (-2%)**\n📉 #{symbol.replace('USDT','')}\nسعر الخروج: {cp:,.4f}")
                    del active_trades[symbol]
    except: pass

async def scout():
    global last_prices, active_trades
    try:
        # جلب بيانات الأسعار اللحظية لسرعة أكبر
        res = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=5).json()
        
        # جلب بيانات السيولة بشكل منفصل كل دقيقة (لتحسين الأداء)
        for item in res:
            sym = item['symbol']
            if sym.endswith('USDT'):
                current_p = float(item['price'])
                
                if sym in last_prices:
                    old_p = last_prices[sym]
                    # تقليل الشرط لـ 0.6% فقط لرصد أي حركة "حرة"
                    change = ((current_p - old_p) / old_p) * 100
                    
                    if change >= 0.6: 
                        # فحص السيولة السريع (فوق 200 ألف)
                        # ملاحظة: في النسخة "الحرة" نركز على السعر أكثر
                        t = get_targets(current_p)
                        active_trades[sym] = {'entry': current_p, 'target': t['target'], 'stop': t['stop']}
                        
                        msg = (f"🔥 **حركة نشطة رُصدت!**\n"
                               f"✅ **العملة:** #{sym.replace('USDT','')}\n"
                               f"📈 صعود لحظي: +{change:.2f}%\n"
                               f"━━━━━━━━━━━━━━\n"
                               f"📥 دخول: {current_p:,.4f}\n"
                               f"🎯 هدف (3%): {t['target']:,.4f}\n"
                               f"🛑 ستوب (2%): {t['stop']:,.4f}\n"
                               f"━━━━━━━━━━━━━━\n"
                               f"⚡️ *وضع الحرية: صيد سريع*")
                        await bot.send_message(CHAT_ID, msg)
                
                last_prices[sym] = current_p
    except: pass

async def main_loop():
    while True:
        await scout()
        await monitor_trades()
        await asyncio.sleep(15) # زيادة سرعة الفحص لـ 15 ثانية

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    asyncio.run(main_loop())
