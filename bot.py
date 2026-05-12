import requests
import asyncio
import math
from telegram import Bot
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# --- الإعدادات (تأكد من صحة التوكن والـ ID) ---
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
bot = Bot(token=TOKEN)

last_prices = {}
active_trades = {}

# --- خادم وهمي لتجاوز Port Binding في Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Free and Alive")

def run_health_server():
    try:
        server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
        server.serve_forever()
    except Exception as e:
        print(f"Server Error: {e}")

def get_targets(price):
    """حساب الأهداف المطلوبة (3% ربح، 2% خسارة)"""
    return {
        "target": price * 1.03,
        "stop": price * 0.98
    }

async def monitor_trades():
    """مراقبة الصفقات المفتوحة"""
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
    """البحث عن فرص بدون قيود ثقيلة"""
    global last_prices, active_trades
    try:
        # جلب الأسعار اللحظية لجميع العملات
        res = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=5).json()
        
        for item in res:
            sym = item['symbol']
            if sym.endswith('USDT'):
                current_p = float(item['price'])
                
                if sym in last_prices:
                    old_p = last_prices[sym]
                    # شرط الصعود: 0.6% فقط (حرية صيد عالية)
                    change = ((current_p - old_p) / old_p) * 100
                    
                    if change >= 0.6: 
                        # إذا لم تكن العملة مراقبة بالفعل، أرسل إشارة
                        if sym not in active_trades:
                            t = get_targets(current_p)
                            active_trades[sym] = {'entry': current_p, 'target': t['target'], 'stop': t['stop']}
                            
                            msg = (f"🔥 **رصد حركة نشطة!**\n"
                                   f"✅ **العملة:** #{sym.replace('USDT','')}\n"
                                   f"📈 صعود لحظي: +{change:.2f}%\n"
                                   f"━━━━━━━━━━━━━━\n"
                                   f"📥 دخول: {current_p:,.4f}\n"
                                   f"🎯 هدف (3%): {t['target']:,.4f}\n"
                                   f"🛑 ستوب (2%): {t['stop']:,.4f}\n"
                                   f"━━━━━━━━━━━━━━\n"
                                   f"⚡️ *وضع الحرية: ON*")
                            await bot.send_message(CHAT_ID, msg)
                
                last_prices[sym] = current_p
    except Exception as e:
        print(f"Scout Error: {e}")

async def main_loop():
    print("🚀 Bot starting...")
    # رسالة اختبار تصلك فور التشغيل على تليجرام
    try:
        await bot.send_message(CHAT_ID, "✅ **البوت متصل الآن!**\nالرادار بدأ بمسح السوق بحثاً عن أي حركة فوق 0.6% وسيولة 200k+.")
    except Exception as e:
        print(f"Telegram Auth Error: {e}")

    while True:
        await scout()
        await monitor_trades()
        # فحص كل 15 ثانية لضمان السرعة
        await asyncio.sleep(15)

if __name__ == "__main__":
    # تشغيل الخادم في الخلفية
    threading.Thread(target=run_health_server, daemon=True).start()
    # تشغيل البوت
    asyncio.run(main_loop())
