import requests
import asyncio
import feedparser
from telegram import Bot

# --- الإعدادات ---
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
bot = Bot(token=TOKEN)

def get_price_backup(symbol):
    """جلب السعر بدون مكتبات ثقيلة (عبر API مباشر) لتجنب الحظر"""
    try:
        sym = symbol.replace('/', '')
        res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={sym}", timeout=5).json()
        return float(res['price'])
    except:
        try:
            # مصدر احتياطي ثاني (CoinGecko)
            res = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd").json()
            return res[symbol.lower()]['usd']
        except: return None

async def fetch_news_rss():
    try:
        feed = feedparser.parse("https://cointelegraph.com/rss")
        news_items = []
        for entry in feed.entries[:3]:
            title = entry.title
            sentiment = "🐂 Bull" if any(w in title.lower() for w in ['up', 'gain', 'high', 'buy', 'etf', 'bull', 'rally']) else "🐻 Bear" if any(w in title.lower() for w in ['down', 'fall', 'low', 'sell', 'hack', 'crash', 'drop']) else "⚖️ Neu"
            news_items.append(f"• {title} **[{sentiment}]**")
        return "\n".join(news_items)
    except: return "⚠️ عطل في محرك الأخبار."

async def get_market_status():
    try:
        res = requests.get("https://api.coinlore.net/api/global/", timeout=10).json()[0]
        # إضافة لمسة تحليل ذكي
        btcd = float(res['btc_d'])
        status = "🔴 Risk-Off (السيولة في البيتكوين فقط)" if btcd > 55 else "🟢 Altseason Potential"
        return f"📊 **هيكل السوق:**\n- استحواذ BTC: {btcd}%\n- الحالة: {status}"
    except: return "📊 جاري تحديث بيانات السوق..."

async def main():
    print("🚀 نظام الاستخبارات 1.4 ينطلق...")
    while True:
        # جلب الأسعار يدوياً لتجنب حظر CCXT
        btc_p = get_price_backup("BTCUSDT")
        sol_p = get_price_backup("SOLUSDT")
        
        signal_text = "🔎 جاري فحص السيولة..."
        if btc_p and sol_p:
            signal_text = (f"🚨 **BTC/USDT**: {btc_p}$\n"
                           f"🚨 **SOL/USDT**: {sol_p}$\n"
                           f"💡 *نصيحة:* إذا BTC فوق 65k و BTC.D ينخفض، ابدأ LONG عملات بديلة.")

        report = (
            f"🧠 **نظام الاستخبارات (AI - المرحلة 1.4)**\n"
            f"━━━━━━━━━━━━━━\n"
            f"{await get_market_status()}\n"
            f"━━━━━━━━━━━━━━\n"
            f"🌍 **أخبار الكريبتو والجيوسياسة:**\n{await fetch_news_rss()}\n"
            f"━━━━━━━━━━━━━━\n"
            f"⚡ **الأسعار والسيولة اللحظية:**\n{signal_text}\n"
            f"━━━━━━━━━━━━━━\n"
            f"⚠️ **إدارة مخاطر:** وقف الخسارة مقدس.\n"
            f"⏰ تحديث كل 15 دقيقة"
        )
        
        try:
            await bot.send_message(chat_id=CHAT_ID, text=report, parse_mode='Markdown')
        except: pass
        
        await asyncio.sleep(900)

if __name__ == "__main__":
    asyncio.run(main())
