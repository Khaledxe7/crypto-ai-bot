import requests
import asyncio
from telegram import Bot

# --- الإعدادات (تأكد من صحة الآيدي والتوكن) ---
TOKEN = "7330089069:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"

bot = Bot(token=TOKEN)

async def get_market_analysis():
    try:
        # جلب بيانات السوق العالمية
        response = requests.get("https://api.coingecko.com/api/v3/global", timeout=10).json()
        data = response['data']
        
        btc_d = data['market_cap_percentage']['btc']
        usdt_d = data['market_cap_percentage'].get('usdt', 4.1)
        total_mcap = data['total_market_cap']['usd'] / 1e12

        score = 0
        notes = ""

        # تحليل السيولة (USDT.D)
        if usdt_d < 4.4:
            score += 40
            notes += "✅ السيولة تدخل السوق (التيثر ينخفض)\n"
        else:
            score -= 10
            notes += "⚠️ الناس بتهرب للكاش (التيثر مرتفع)\n"

        # تحليل الاستحواذ (BTC.D)
        if btc_d < 52:
            score += 30
            notes += "🔥 وقت العملات البديلة (Altcoin Season)\n"
        else:
            notes += "₿ السيولة مركزة في البيتكوين حالياً\n"

        # القرار
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
        return f"❌ عذراً، فشل جلب البيانات حالياً.\nالسبب: {e}"

async def main():
    print("🚀 البوت بدأ العمل الآن...")
    
    # أول رسالة يرسلها فوراً عند التشغيل
    first_message = await get_market_analysis()
    try:
        await bot.send_message(chat_id=CHAT_ID, text=first_message, parse_mode='Markdown')
        print("✅ أول رسالة تم إرسالها بنجاح!")
    except Exception as e:
        print(f"❌ خطأ في الإرسال الأول: {e}")

    while True:
        # ينتظر 4 ساعات قبل التحديث القادم (14400 ثانية)
        await asyncio.sleep(14400)
        
        message = await get_market_analysis()
        try:
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
            print("✅ تم إرسال التحديث الدوري.")
        except Exception as e:
            print(f"❌ خطأ في الإرسال الدوري: {e}")

if __name__ == "__main__":
    asyncio.run(main())
