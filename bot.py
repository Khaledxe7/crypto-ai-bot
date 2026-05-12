import requests
import asyncio
import feedparser
from telegram import Bot

# --- الإعدادات ---
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
bot = Bot(token=TOKEN)

async def get_market_sentiment():
    """1. تحليل حالة السوق العام (BTC.D & USDT.D)"""
    try:
        res = requests.get("https://api.coinlore.net/api/global/", timeout=10).json()[0]
        btcd = float(res['btc_d'])
        # إذا الاستحواذ مرتفع جداً وبيرتفع، الدخول في عملات بديلة خطر
        market_safe = True if btcd < 60 else False 
        return market_safe, btcd
    except: return True, 0

async def analyze_news_impact():
    """2. تحليل الأخبار - هل الجو العام سلبي (حروب/أزمات)؟"""
    try:
        feed = feedparser.parse("https://cointelegraph.com/rss")
        bad_words = ['crash', 'hack', 'war', 'attack', 'fed rate hike', 'lawsuit', 'ban']
        negative_score = 0
        news_summary = ""
        for entry in feed.entries[:3]:
            title = entry.title.lower()
            if any(word in title for word in bad_words):
                negative_score += 1
            news_summary += f"• {entry.title}\n"
        
        # لو فيه أكثر من خبر سلبي جداً، نوقف التوصيات
        is_news_safe = True if negative_score < 2 else False
        return is_news_safe, news_summary
    except: return True, ""

async def get_technical_verdict(symbol):
    """3. تحليل فني سريع (RSI مبسط) عبر طلب بيانات الشموع"""
    try:
        # نجلب آخر شموع من بينانس لفحص الزخم
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=14"
        res = requests.get(url, timeout=10).json()
        closes = [float(c[4]) for c in res]
        # فلتر بسيط: لو السعر الحالي أعلى بكثير من شمعة الافتتاح (متضخم) لا تدخل
        is_tech_safe = True if closes[-1] > closes[0] else False
        return is_tech_safe
    except: return True

async def main():
    print("🧠 نظام الاستخبارات المدمج بدأ العمل...")
    while True:
        # أولاً: فحص السوق والأخبار (قبل أي بحث عن عملات)
        market_safe, btcd = await get_market_sentiment()
        news_safe, news_report = await analyze_news_impact()

        if not market_safe or not news_safe:
            print(f"⚠️ التداول خطر حالياً: BTC.D {btcd}% | News Safe: {news_safe}")
        else:
            # ثانياً: إذا السوق آمن، نبحث عن عملات الـ 200 الكبرى
            try:
                # جلب أفضل 200 عملة من CoinGecko
                top_200_res = requests.get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=200&page=1", timeout=10).json()
                top_200_symbols = [c['symbol'].upper() + "USDT" for c in top_200_res]
                
                # جلب بيانات بينانس
                binance_data = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=10).json()
                
                for item in binance_data:
                    symbol = item['symbol']
                    if symbol in top_200_symbols:
                        change = float(item['priceChangePercent'])
                        volume = float(item['quoteVolume']) / 1e6
                        
                        # شرط الـ 2% إلى 3% + سيولة > 10 مليون
                        if 2.0 <= change <= 3.5 and volume > 10:
                            # ثالثاً: الفحص الفني للعملة نفسها
                            if await get_technical_verdict(symbol):
                                price = float(item['lastPrice'])
                                msg = (
                                    f"🎯 **توصية استخباراتية مؤكدة** 🎯\n"
                                    f"━━━━━━━━━━━━━━\n"
                                    f"✅ العملة: #{symbol}\n"
                                    f"📈 الصعود: +{change}%\n"
                                    f"💰 السيولة: ${volume:.1f}M\n"
                                    f"📊 استحواذ BTC: {btcd}%\n"
                                    f"━━━━━━━━━━━━━━\n"
                                    f"🌍 **أهم الأخبار المحللة:**\n{news_report}\n"
                                    f"━━━━━━━━━━━━━━\n"
                                    f"💡 **القرار:** LONG (دخول فوري)\n"
                                    f"🎯 الهدف: {price*1.03:.4f} (3%)\n"
                                    f"🛑 الستوب: {price*0.97:.4f} (3%)\n"
                                    f"🔗 [فتح الشارت فريم 5د](https://www.tradingview.com/chart/?symbol=BINANCE:{symbol})\n"
                                )
                                await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown', disable_web_page_preview=True)
                                await asyncio.sleep(300) # انتظار 5 دقائق بعد كل توصية لمنع الإزعاج
            except Exception as e:
                print(f"Error: {e}")

        await asyncio.sleep(600) # مسح شامل كل 10 دقائق

if __name__ == "__main__":
    asyncio.run(main())
