import requests
import asyncio
from telegram import Bot

# --- بياناتك بعد التصليح ---
TOKEN = "7330089069:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"

bot = Bot(token=TOKEN)

async def get_market_analysis():
    try:
        response = requests.get("https://api.coingecko.com/api/v3/global").json()
        data = response['data']
        btc_d = data['market_cap_percentage']['btc']
        usdt_d = data['market_cap_percentage'].get('usdt', 4.2)
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
            f"📊 *تقرير السوق الذكي*\n\n"
            f"🔹 BTC.D: {btc_d:.1f}%\n"
            f"🔹 USDT.D: {usdt_d:.1f}%\n"
            f"🔹 Total: ${total_mcap:.2f}T\n\n"
            f"📝 {notes}\n"
            f"📢 القرار: {decision}"
        )
        return report
    except:
        return "❌ خطأ في البيانات"

async def main():
    print("Bot is starting...")
    while True:
        message = await get_market_analysis()
        try:
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
            print("Done!")
        except Exception as e:
            print(f"Error: {e}")
        await asyncio.sleep(14400) # كل 4 ساعات

if __name__ == "__main__":
    asyncio.run(main())
