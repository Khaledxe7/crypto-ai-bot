import requests
import time
import asyncio
from telegram import Bot

# --- الإعدادات الصحيحة ---
TOKEN = "7330089069:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"

bot = Bot(token=TOKEN)

async def get_market_analysis():
    try:
        # جلب البيانات من مصدر مفتوح (CoinGecko)
        response = requests.get("https://api.coingecko.com/api/v3/global").json()
        data = response['data']
        
        btc_d = data['market_cap_percentage']['btc'] 
        usdt_d = data['market_cap_percentage'].get('usdt', 4.2) 
        total_mcap = data['total_market_cap']['usd'] / 1e12 

        score = 0
        notes = ""

        if usdt_d < 4.4:
            score += 40
            notes += "✅ السيولة تدخل السوق (التيثر ينخفض)\n"
        else:
            score -= 10
            notes += "⚠️ الناس بتهرب للكاش (التيثر مرتفع)\n"

        if btc_d < 52:
            score += 30
            notes += "🔥 وقت العملات البديلة (هيمنة البيتكوين منخفضة)\n"
        else:
            notes += "₿ السيولة مركزة في البيتكوين حالياً\n"

        if score >= 60:
            decision = "🚀 توصية: LONG / دخول قوي"
        elif score >= 30:
            decision = "⚖️ توصية: تجميع هادئ"
        else:
            decision = "📉 توصية: خروج / كاش (RISK OFF)"

        report = (
            f"🤖 *تحليل الذكاء الاصطناعي للسوق:*\n\n"
            f"📊 هيمنة BTC: {btc_d:.1f}%\n"
            f"💵 هيمنة USDT: {usdt_d:.1f}%\n"
            f"💰 السيولة الكلية: ${total_mcap:.2f}T\n\n"
            f"📝 *التحليل:*\n{notes}\n"
            f"📢 *القرار:* {decision}"
        )
        return report
    except Exception as e:
        return f"❌ فشل في جلب البيانات: {e}"

async def main():
    print("Bot is starting...")
    while True:
        message = await get_market_analysis()
        try:
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
            print("Message sent successfully!")
        except Exception as e:
            print(f"Send error: {e}")
            
        # تحديث كل 4 ساعات
        await asyncio.sleep(14400)

if __name__ == "__main__":
    asyncio.run(main())
