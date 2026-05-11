import requests
import asyncio
from telegram import Bot

# --- البيانات الصحيحة 100% ---
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"

bot = Bot(token=TOKEN)

async def get_market_analysis():
    try:
        response = requests.get("https://api.coingecko.com/api/v3/global", timeout=10).json()
        data = response['data']
        btc_d = data['market_cap_percentage']['btc']
        usdt_d = data['market_cap_percentage'].get('usdt', 4.1)
        total_mcap = data['total_market_cap']['usd'] / 1e12

        score = 0
        notes = ""
        if usdt_d < 4.4:
            score += 40
            notes += "✅ السيولة تدخل السوق\n"
        else:
            score -= 10
            notes += "⚠️ الناس بتهرب للكاش\n"

        if btc_d < 52:
            score += 30
            notes += "🔥 وقت العملات البديلة\n"
        else:
            notes += "₿ السيولة في البيتكوين\n"

        decision = "🚀 LONG" if score >= 60 else "⚖️ WAIT" if score >= 30 else "📉 RISK OFF"

        report = (
            f"🤖 *تحليل الذكاء الاصطناعي للسوق:*\n\n"
            f"📊 هيمنة BTC: {btc_d:.1f}%\n"
            f"💵 هيمنة USDT: {usdt_d:.1f}%\n"
            f"💰 السيولة: ${total_mcap:.2f}T\n\n"
            f"📢 *القرار:* {decision}"
        )
        return report
    except Exception as e:
        return f"❌ خطأ في البيانات: {e}"

async def main():
    print("🚀 البوت انطلق بالتوكن الجديد!")
    # إرسال رسالة فورية عند التشغيل
    try:
        msg = await get_market_analysis()
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
        print("✅ وصلت الرسالة لتليجرام!")
    except Exception as e:
        print(f"❌ فشل الإرسال: {e}")

    while True:
        await asyncio.sleep(14400) # تحديث كل 4 ساعات
        msg = await get_market_analysis()
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')

if __name__ == "__main__":
    asyncio.run(main())
