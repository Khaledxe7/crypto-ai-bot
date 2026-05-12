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

# خادم وهمي لـ Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Active - 20k Liquidity Mode")

def run_health_server():
    try:
        server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
        server.serve_forever()
    except: pass

def get_targets(price):
    return {
        "target": price * 1.03, # هدف 3%
        "stop": price * 0.98    # ستوب 2%
    }

async def scout():
    global last_prices, active_trades
    try:
        # جلب بيانات 24 ساعة للتحقق من السيولة
        tickers = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=5).json()
        
        for item in tickers:
            sym = item['symbol']
            if sym.endswith('USDT'):
                vol = float(item['quoteVolume'])
                current_p = float(item['lastPrice'])
                
                # الفلتر الجديد: سيولة ابتداءً من 20 ألف دولار
                if vol >= 20000:
                    if sym in last_prices:
                        old_p = last_prices[sym]
                        change = ((current_p - old_p) / old_p) * 100
                        
                        # رصد حركة فوق 0.6%
                        if change >= 0.6 and sym not in active_trades:
                            t = get_targets(current_p)
                            active_trades[sym] = {'entry': current_p, 'target': t['target'], 'stop': t['stop']}
                            
                            vol_display = f"{vol/1e3:.1f}K"
                            msg = (f"🔍 **رادار السيولة المفتوحة ($20k+):**\n"
                                   f"✅ **العملة:** #{sym.replace('USDT','')}\n"
                                   f"📈 القفزة: +{change:.2f}%\n"
                                   f"💰 السيولة: ${vol_display}\n"
                                   f"━━━━━━━━━━━━━━\n"
                                   f"📥 دخول: {current_p:,.4f}\n"
                                   f"🎯 هدف (3%): {t['target']:,.4f}\n"
                                   f"🛑 ستوب (2%): {t['stop']:,.4f}\n"
                                   f"━━━━━━━━━━━━━━")
                            await bot.send_message(CHAT_ID, msg)
                    
                    last_prices[sym] = current_p
    except: pass

async def main_loop():
    try:
        await bot.send_message(CHAT_ID, "✅ **تم تفعيل وضع السيولة المنخفضة ($20k+)!**\nالرادار الآن يراقب كل شيء.")
    except: pass

    while True:
        await scout()
        await asyncio.sleep(15)

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    asyncio.run(main_loop())
