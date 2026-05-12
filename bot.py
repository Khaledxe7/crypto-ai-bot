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
        self.wfile.write(b"Strict MEXC Bot is Running")

def run_health_server():
    try:
        server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
        server.serve_forever()
    except: pass

def get_pro_targets(price):
    """تحليل رقمي صارم للأهداف"""
    root = math.sqrt(price)
    return {
        "target_3pct": price * 1.03,    # هدفك الأساسي
        "gann_90": (root + 0.5)**2,     # زاوية جان 90 لتأكيد القوة
        "stop": price * 0.98            # وقف خسارة صارم 2%
    }

async def scout_strict():
    global last_prices, active_trades
    try:
        url = "https://api.mexc.com/api/v3/ticker/24hr"
        res = requests.get(url, timeout=10).json()
        
        for item in res:
            sym = item['symbol']
            if sym.endswith('USDT'):
                vol = float(item['quoteVolume'])
                current_p = float(item['lastPrice'])
                
                # --- الفلتر الصارم ---
                # 1. السيولة لا تقل عن 500 ألف دولار
                if vol >= 500000:
                    if sym in last_prices:
                        old_p = last_prices[sym]
                        change = ((current_p - old_p) / old_p) * 100
                        
                        # 2. قوة الانفجار لا تقل عن 1.2% (شمعة زخم حقيقية)
                        if change >= 1.2 and sym not in active_trades:
                            t = get_pro_targets(current_p)
                            active_trades[sym] = {'entry': current_p, 'target': t['target_3pct'], 'stop': t['stop']}
                            
                            msg = (f"🎯 **إشارة صارمة (زخم عالي):**\n"
                                   f"✅ **العملة:** #{sym.replace('USDT','')}\n"
                                   f"🔥 قوة الانفجار: +{change:.2f}%\n"
                                   f"💰 السيولة: ${vol/1e6:.2f}M\n"
                                   f"━━━━━━━━━━━━━━\n"
                                   f"📥 دخول: {current_p:,.6f}\n"
                                   f"🎯 هدف (3%): {t['target_3pct']:,.6f}\n"
                                   f"📐 زاوية جان 90: {t['gann_90']:,.6f}\n"
                                   f"🛑 ستوب (2%): {t['stop']:,.6f}\n"
                                   f"━━━━━━━━━━━━━━\n"
                                   f"⚠️ *الحالة: اختراق فني مدعوم بسيولة ضخمة*")
                            await bot.send_message(CHAT_ID, msg)
                    
                    last_prices[sym] = current_p
    except Exception as e:
        print(f"Error: {e}")

async def main_loop():
    try:
        await bot.send_message(CHAT_ID, "⚖️ **تم تفعيل النظام الصارم (V4.7)**\n\n🔹 المنصة: MEXC\n🔹 السيولة: +$500k\n🔹 الانفجار: +1.2%\n📍 الأهداف: 3% ربح / 2% ستوب")
    except: pass

    while True:
        await scout_strict()
        await asyncio.sleep(15) # فحص سريع جداً لصيد اللحظة

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    asyncio.run(main_loop())
