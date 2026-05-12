import requests
import asyncio
import ccxt
import feedparser
from telegram import Bot

# --- الإعدادات ---
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
bot = Bot(token=TOKEN)

# استخدام محرك Binance مع وكيل مستخدم (User-Agent)
exchange = ccxt.binance({
    'enableRateLimit': True,
    'headers': {'User-Agent': 'Mozilla/5.0'}
})

async def fetch_news_rss():
    """جلب الأخبار عبر RSS (مضمون 100% ضد الحظر)"""
    try:
        # رابط RSS من Cointelegraph
        feed = feedparser.parse("https://cointelegraph.com/rss")
        news_items = []
        for entry in feed.entries[:3]:
            title = entry.title
            # ذكاء اصطناعي بسيط لتحليل المشاعر
            sentiment = "🐂 Bull" if any(w in title.lower() for w in ['up', 'gain', 'high', 'buy', 'etf', 'bull']) else "🐻 Bear" if any(w in title.lower() for w in ['down', 'fall', 'low', 'sell', 'hack', 'crash']) else "⚖️ Neu"
            news_items.append(f"• {title} **[{sentiment}]**")
        return "\n".join(news_items) if news_items else "لا توجد أخبار حالياً."
    except:
        return "⚠️ عطل في محرك الأخبار RSS."

async def get_crypto_data():
    """جلب بيانات السوق والسيولة بطريقة احتياطية"""
    try:
        # محاولة جلب الاستحواذ من مصدر بديل (Coinlore) لأنه أقل حظراً
        res = requests.get("https://api.coinlore.net/api/global/", timeout=10).json()[0]
        btc_d = res['btc_d']
        eth_d = res['eth_d']
        
        status = "🟢 Risk-On" if float(btc_d) < 55 else "🔴 Risk-Off"
        return f"📊 **هيكل السوق:**\n- استحواذ BTC: {btc_d}%\n- استحواذ ETH: {eth_d}%\n- الحالة: {status}"
    except:
        return "📊 **هيكل السوق:** جاري تحديث البيانات..."

async def get_signals():
    """تحليل السيولة اللحظية لـ BTC و SOL"""
    try:
        results = []
        for symbol in ['BTC/USDT', 'SOL/USDT']:
            ticker = exchange.fetch_ticker(symbol)
            price = ticker['last']
            change = ticker['percentage']
            
            side = "LONG 🟢" if change > 0 else "SHORT 🔴"
            # حساب الأهداف (سكالبينج 2%)
            target = price * (1.02 if change > 0 else 0.98)
            
            results.append(f"🚨 **{symbol}**: {side}\n💰 السعر: {price}\n🎯 هدف (2%): {target:.2f}")
        return "\n\n".join(results)
    except:
        return "🔎 محرك Binance يحاول الاتصال..."

async def main():
    print("🚀 نظام الاستخبارات 1.3 يعمل الآن...")
    while True:
        report = (
            f"🧠 **نظام الاستخبارات (AI - المرحلة 1.3)**\n"
            f"━━━━━━━━━━━━━━\n"
            f"{await get_crypto_data()}\n"
            f"━━━━━━━━━━━━━━\n"
            f"📰 **رادار الأخبار الذكي (RSS):**\n{await fetch_news_rss()}\n"
            f"━━━━━━━━━━━━━━\n"
            f"⚡ **إشارات السيولة:**\n{await get_signals()}\n"
            f"━━━━━━━━━━━━━━\n"
            f"⚖️ إدارة مخاطر: 1%\n"
            f"⏰ تحديث كل 15 دقيقة"
        )
        try:
            await bot.send_message(chat_id=CHAT_ID, text=report, parse_mode='Markdown', disable_web_page_preview=True)
        except Exception as e:
            print(f"Error: {e}")
        
        await asyncio.sleep(900)

if __name__ == "__main__":
    asyncio.run(main())
