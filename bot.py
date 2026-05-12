import requests
import asyncio
import feedparser
import json
from telegram import Bot

# --- الإعدادات ---
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
bot = Bot(token=TOKEN)

def get_tv_price(symbol):
    """جلب السعر من محرك TradingView العام"""
    try:
        # محاكاة طلب من شارت تريدنج فيو
        url = f"https://scanner.tradingview.com/crypto/scan"
        payload = {
            "symbols": {"tickers": [f"BINANCE:{symbol}"]},
            "columns": ["lp", "change", "volume"]
        }
        res = requests.post(url, json=payload, timeout=10).json()
        data = res['data'][0]['d']
        return {
            "price": data[0],
            "change": data[1],
            "vol": data[2]
        }
    except:
        # حل احتياطي إذا فشل التيكر الخاص
        try:
            res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5).json()
            return {"price": float(res['price']), "change": 0, "vol": 0}
        except: return None

async def fetch_global_news():
    """رادار الأخبار من كبار المصادر (Cointelegraph & News)"""
    try:
        feed = feedparser.parse("https://cointelegraph.com/rss")
        news = []
        for entry in feed.entries[:3]:
            title = entry.title
            # ذكاء اصطناعي بسيط لتحليل الكلمات المفتاحية
            impact = "🔥 عالي" if any(x in title.lower() for x in ['sec', 'fed', 'etf', 'war', 'crash', 'huge']) else "⚡ متوسط"
            news.append(f"• {title} [تأثير: {impact}]")
        return "\n".join(news)
    except: return "⚠️ جاري تحديث رادار الأخبار..."

async def market_sentiment():
    """تحليل استحواذ البيتكوين والسيولة"""
    try:
        res = requests.get("https://api.coinlore.net/api/global/", timeout=10).json()[0]
        btcd = res['btc_d']
        # ربط الاستحواذ بالقرار
        advice = "💰 وقت العملات البديلة" if float(btcd) < 52 else "₿ البيتكوين يقود السوق"
        return f"📊 **هيكل السيولة:**\n- استحواذ BTC: {btcd}%\n- التوجه: {advice}"
    except: return "📊 جاري تحليل السيولة..."

async def main():
    print("🚀 نظام استخبارات TradingView انطلق...")
    while True:
        # جلب بيانات أهم العملات من محرك تريدنج فيو
        btc = get_tv_price("BTCUSDT")
        sol = get_tv_price("SOLUSDT")
        eth = get_tv_price("ETHUSDT")

        prices_text = "⚡ **الأسعار والزخم (TradingView):**\n"
        if btc:
            prices_text += f"₿ BTC: ${btc['price']:,.0f} ({btc['change']:.2f}%)\n"
        if sol:
            prices_text += f"☀️ SOL: ${sol['price']:.2f} ({sol['change']:.2f}%)\n"
        if eth:
            prices_text += f"💎 ETH: ${eth['price']:,.0f} ({eth['change']:.2f}%)\n"

        report = (
            f"🧠 **نظام الاستخبارات (المرحلة 1.5)**\n"
            f"━━━━━━━━━━━━━━\n"
            f"{await market_sentiment()}\n"
            f"━━━━━━━━━━━━━━\n"
            f"🌍 **أهم المستجدات العالمية:**\n{await fetch_global_news()}\n"
            f"━━━━━━━━━━━━━━\n"
            f"{prices_text}\n"
            f"━━━━━━━━━━━━━━\n"
            f"📢 **توصية النظام:** {'إغلاق صفقات (Risk-Off)' if btc and btc['change'] < -2 else 'بحث عن فرص (Scalping)'}\n"
            f"⏰ تحديث كل 15 دقيقة"
        )

        try:
            await bot.send_message(chat_id=CHAT_ID, text=report, parse_mode='Markdown')
            print("✅ التقرير أُرسل بنجاح.")
        except Exception as e:
            print(f"❌ خطأ إرسال: {e}")

        await asyncio.sleep(900)

if __name__ == "__main__":
    asyncio.run(main())
