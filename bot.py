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

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Extreme Strict MEXC Bot is Running")

def run_health_server():
    try:
        server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
        server.serve_forever()
    except: pass

def get_pro_targets(price):
    return {
        "target": price * 1.03,
        "stop": price * 0.98
    }

async def scout_extreme():
    global last_prices, active_trades
    try:
        url = "https://api.mexc.com/api/v3/ticker/24hr"
        res = requests.get(url, timeout=10).json()
        
        for item in res:
            sym = item['symbol']
            if sym.endswith('USDT'):
                vol = float(item['quoteVolume'])
                current_p = float(item['lastPrice'])
                
                # --- الفلتر الصارم الأقصى ---
                # سيولة +1 مليون دولار + انفجار +1.5%
                if vol >= 1000000: 
                    if sym in last_prices:
                        old_p = last_prices[sym]
                        change = ((current_p - old_p) / old_p) * 100
                        
                        if change >= 1.5 and sym not in active_trades:
                            t = get_pro_targets(current_p)
                            active_trades[sym] = {'entry': current_p, 'target': t['target'], 'stop': t['stop']}
                            
                            msg = (f"🛡️ **إشارة حيتان (الوضع الصارم الأقصى):**\n"
                                   f"✅ **العملة:** #{sym.replace('USDT','')}\n"
                                   f"⚡️ قوة الزخم: +{change:.2f}%\n"
                                   f"💰 السيولة: ${vol/1e6:.2f}M\n"
                                   f"━━━━━━━━━━━━━━\n"
                                   f"📥 دخول ماركت: {current_p:,.6f}\n"
                                   f"🎯 هدف (3%): {t['target']:,.6f}\n"
                                   f"🛑 ستوب (2%): {t['stop']:,.6f}\n"
                                   f"━━━━━━━━━━━━━━\n"
                                   f"🔥 *نظام الفلترة: صارم جداً*")
                            await bot.send_message(CHAT_ID, msg)
                    
                    last_prices[sym] = current_p
    except Exception as e:
        print(f"Error: {e}")

async def main_loop():
    try:
        await bot.send_message(CHAT_ID, "🛡️ **تم تفعيل الوضع الصارم الأقصى (V4.8)**\n\n⚠️ التنبيهات ستكون قليلة ولكنها عالية الجودة جداً.\n🔹 السيولة: +$1M\n🔹 الانفجار: +1.5%")
    except: pass

    while True:
        await scout_extreme()
        await asyncio.sleep(10) # فحص فائق السرعة كل 10 ثواني

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    asyncio.run(main_loop())
