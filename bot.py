import requests
import asyncio
import math
from telegram import Bot

# --- الإعدادات ---
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
bot = Bot(token=TOKEN)

last_prices = {}
active_trades = {}  # لتخزين الصفقات المفتوحة ومراقبة أهدافها

async def monitor_active_trades():
    """مراقبة الصفقات المفتوحة لإرسال تنبيهات الهدف والستوب"""
    global active_trades
    try:
        if not active_trades:
            return

        res = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=10).json()
        prices = {item['symbol']: float(item['price']) for item in res if item['symbol'].endswith('USDT')}

        for symbol, trade in list(active_trades.items()):
            if symbol in prices:
                current_p = prices[symbol]
                entry_p = trade['entry']
                target_p = trade['target']
                stop_p = trade['stop']

                # فحص الهدف (3%)
                if current_p >= target_p:
                    msg = f"✅ **تم تحقيق الهدف!**\n💰 العملة: #{symbol.replace('USDT','')}\n📈 الربح: +3.00%\n🚀 السعر الحالي: {current_p:,.4f}"
                    await bot.send_message(chat_id=CHAT_ID, text=msg)
                    del active_trades[symbol] # إغلاق المراقبة بعد الهدف

                # فحص الستوب (2%)
                elif current_p <= stop_p:
                    msg = f"🛑 **ضرب الستوب لوز!**\n📉 العملة: #{symbol.replace('USDT','')}\n📉 الخسارة: -2.00%\n⚠️ السعر الحالي: {current_p:,.4f}"
                    await bot.send_message(chat_id=CHAT_ID, text=msg)
                    del active_trades[symbol] # إغلاق المراقبة بعد الستوب
    except Exception as e:
        print(f"Monitor Error: {e}")

async def scout_market():
    global last_prices, active_trades
    try:
        res = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=10).json()
        
        for item in res:
            symbol = item['symbol']
            if symbol.endswith('USDT'):
                volume = float(item['quoteVolume'])
                current_price = float(item['lastPrice'])
                
                if volume >= 200000:
                    if symbol in last_prices:
                        change = ((current_price - last_prices[symbol]) / last_prices[symbol]) * 100
                        
                        if change >= 1.1:
                            # حساب الهدف والستوب المطلوبين (3% ربح و 2% خسارة)
                            target = current_price * 1.03
                            stop = current_price * 0.98
                            
                            # إضافة العملة للمراقبة اللحظية
                            active_trades[symbol] = {
                                'entry': current_price,
                                'target': target,
                                'stop': stop
                            }

                            msg = (
                                f"🚀 **إشارة دخول جديدة ($200k+):**\n"
                                f"✅ **العملة:** #{symbol.replace('USDT','')}\n"
                                f"⚡️ **القفزة:** +{change:.2f}%\n"
                                f"━━━━━━━━━━━━━━\n"
                                f"📥 **سعر الدخول:** {current_price:,.4f}\n"
                                f"🎯 **هدف التنبيه (3%):** {target:,.4f}\n"
                                f"🛑 **ستوب التنبيه (2%):** {stop:,.4f}\n"
                                f"━━━━━━━━━━━━━━\n"
                                f"📢 *سأقوم بتنبيهك فور وصول السعر لأي منهما!*"
                            )
                            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
                
                last_prices[symbol] = current_price
    except Exception as e:
        print(f"Scout Error: {e}")

async def main():
    print("🚀 رادار الصيد والتعقب يعمل...")
    await bot.send_message(chat_id=CHAT_ID, text="🤖 **نظام V4.4 (التعقب الآلي):**\n\n✅ تنبيهات الدخول ($200k+)\n✅ تتبع الأهداف (3% ربح)\n✅ تتبع الستوب (2% خسارة)")

    while True:
        await scout_market()        # البحث عن فرص
        await monitor_active_trades() # مراقبة الأهداف
        await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main())
