import requests
import asyncio
import math
from telegram import Bot

# --- الإعدادات ---
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
bot = Bot(token=TOKEN)

last_prices = {}

def get_harmonic_levels(price):
    """حساب مستويات الهارمونيك الذهبية (PRZ - Potential Reversal Zone)"""
    # نسب فيبوناتشي الأساسية للهارمونيك
    prz_886 = price * 1.00886  # نقطة الانعكاس العميق (Deep Crab/Bat)
    prz_786 = price * 1.00786  # نقطة الفراشة (Butterfly)
    prz_1618 = price * 1.01618 # الهدف الانفجاري للموجة
    
    return {
        "d_point": prz_886,
        "butterfly": prz_786,
        "extension": prz_1618
    }

async def scout_market():
    global last_prices
    try:
        # جلب البيانات اللحظية من بينانس
        res = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=10).json()
        
        for item in res:
            symbol = item['symbol']
            if symbol.endswith('USDT'):
                volume = float(item['quoteVolume'])
                current_price = float(item['lastPrice'])
                
                # التركيز على السيولة الطبيعية (100k - 1.5M) لضمان حركة سكالبينج حقيقية
                if 100000 <= volume <= 1500000:
                    if symbol in last_prices:
                        old_price = last_prices[symbol]
                        change = ((current_price - old_price) / old_price) * 100
                        
                        # رصد الشمعة الانفجارية (أكثر من 1.2% في 20 ثانية)
                        if change >= 1.2:
                            harmonic = get_harmonic_levels(current_price)
                            
                            msg = (
                                f"🦋 **رادار الهارمونيك والسيولة (V4.1):**\n"
                                f"✅ **العملة:** #{symbol.replace('USDT','')}\n"
                                f"🔥 **حركة الشمعة:** +{change:.2f}%\n"
                                f"💰 **فوليوم السيولة:** ${volume/1e3:.0f}K\n"
                                f"━━━━━━━━━━━━━━\n"
                                f"🎯 **أهداف الهارمونيك (PRZ):**\n"
                                f"📍 نقطة (Bat/D): {harmonic['d_point']:.4f}\n"
                                f"📍 هدف (Butterfly): {harmonic['butterfly']:.4f}\n"
                                f"🚀 امتداد فيبوناتشي: {harmonic['extension']:.4f}\n"
                                f"━━━━━━━━━━━━━━\n"
                                f"📥 **دخول ماركت:** {current_price:,.4f}\n"
                                f"🛑 **وقف الخسارة:** {current_price * 0.982:,.4f}\n"
                                f"━━━━━━━━━━━━━━\n"
                                f"💡 *التحليل: سيولة عالية + نموذج هارمونيك قيد التكون!*"
                            )
                            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
                
                last_prices[symbol] = current_price
    except Exception as e:
        print(f"Scout Error: {e}")

async def main():
    print("🚀 تشغيل القناص التوافقي...")
    welcome = (
        "🦋 **تم تفعيل محرك الهارمونيك والسيولة V4.1**\n\n"
        "🎯 التركيز: شمعة الانفجار اللحظية\n"
        "📐 التحليل: PRZ & Fibonacci Ratios\n"
        "💰 السيولة: $100k - $1.5M"
    )
    await bot.send_message(chat_id=CHAT_ID, text=welcome)

    while True:
        await scout_market()
        await asyncio.sleep(20) # فحص كل 20 ثانية لصيد "الهارمونيك" في بدايته

if __name__ == "__main__":
    asyncio.run(main())
