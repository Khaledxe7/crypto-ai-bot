import requests
import asyncio
import math
from telegram import Bot
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# --- الإعدادات ---
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
bot = Bot(token=TOKEN)

last_prices = {}
active_trades = {}

# خادم وهمي لـ Render لضمان عدم التوقف
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"MEXC Scalper is Active")

def run_health_server():
    try:
        server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
        server.serve_forever()
    except: pass

def get_targets(price):
    return {
        "target": price * 1.03, # ربح 3%
        "stop": price * 0.98    # خسارة 2%
    }

async def scout_mexc():
    """البحث عن فرص في منصة MEXC"""
    global last_prices, active_trades
    try:
        # رابط API الخاص بأسعار MEXC (بدون توثيق معقد للبحث العام)
        url = "https://api.mexc.com/api/v3/ticker/24hr"
        res = requests.get(url, timeout=10).json()
        
        for item in res:
            sym = item['symbol']
            # نركز على أزواج USDT فقط
            if sym.endswith('USDT'):
                # السيولة في MEXC تُسمى quoteVolume (حجم التداول بالدولار)
                vol = float(item['quoteVolume'])
                current_p = float(item['lastPrice'])
                
                # الفلتر المطلوب: سيولة 20 ألف دولار وما فوق
                if vol >= 20000:
                    if sym in last_prices:
                        old_p = last_prices[sym]
                        change = ((current_p - old_p) / old_p) * 100
                        
                        # رصد صعود سريع 0.6% في دورة الفحص
                        if change >= 0.6 and sym not in active_trades:
                            t = get_targets(current_p)
                            active_trades[sym] = {'entry': current_p, 'target': t['target'], 'stop': t['stop']}
                            
                            vol_display = f"{vol/1e3:.1f}K"
                            msg = (f"💎 **جوهرة من MEXC ($20k+):**\n"
                                   f"✅ **العملة:** #{sym.replace('USDT','')}\n"
                                   f"📈 الانفجار اللحظي: +{change:.2f}%\n"
                                   f"💰 سيولة 24س: ${vol_display}\n"
                                   f"━━━━━━━━━━━━━━\n"
                                   f"📥 دخول: {current_p:,.6f}\n"
                                   f"🎯 هدف (3%): {t['target']:,.6f}\n"
                                   f"🛑 ستوب (2%): {t['stop']:,.6f}\n"
                                   f"━━━━━━━━━━━━━━\n"
                                   f"⚠️ *ملاحظة: تداول MEXC عالي المخاطر!*")
                            await bot.send_message(CHAT_ID, msg)
                    
                    last_prices[sym] = current_p
    except Exception as e:
        print(f"MEXC Error: {e}")

async def main_loop():
    try:
        await bot.send_message(CHAT_ID, "🚀 **تم تحويل الرادار إلى منصة MEXC!**\nجاري البحث عن عملات السيولة المنخفضة ($20k+).")
    except: pass

    while True:
        await scout_mexc()
        # فحص كل 20 ثانية لأن MEXC سريعة التغير
        await asyncio.sleep(20)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    asyncio.run(main_loop())
