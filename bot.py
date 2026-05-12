import requests
import asyncio
import ccxt
from telegram import Bot

# --- الإعدادات ---
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
bot = Bot(token=TOKEN)

# إعداد Binance مع واجهة عامة لتجنب الحظر
exchange = ccxt.binance({'enableRateLimit': True})

async def fetch_breaking_news():
    try:
        # استخدام رابط بديل ومباشر أكثر استقراراً
        url = "https://cryptopanic.com/api/v1/posts/?public=true&filter=important"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15).json()
        news_items = []
        for post in res.get('results', [])[:3]:
            title = post['title']
            # تحليل بسيط للمشاعر (Sentiment) مبدئي
            sentiment = "🐂 Bullish" if any(word in title.lower() for word in ['launch', 'buy', 'pump', 'listing', 'partnership']) else "🐻 Bearish" if any(word in title.lower() for word in ['dump', 'hack', 'delist', 'sell', 'lawsuit']) else "⚖️ Neutral"
            news_items.append(f"• {title} ({sentiment})")
        return "\n".join(news_items) if news_items else "لا توجد أخبار عاجلة."
    except:
        return "⚠️ المصدر مشغول.. جاري إعادة المحاولة لاحقاً."

async def analyze_market_liquidity():
    try:
        # جلب البيانات الأساسية من مصدر احتياطي
        res = requests.get("https://api.coingecko.com/api/v3/global", timeout=10).json()
        data = res['data']
        btc_d = data['market_cap_percentage']['btc']
        usdt_d = data['market_cap_percentage'].get('usdt', 6.8)
        
        status = "🟢 دخول سيولة (Risk-On)" if usdt_d < 4.5 else "🔴 خروج سيولة (Risk-Off)"
        return f"📊 **هيكل السوق:**\n- استحواذ BTC: {btc_d:.1f}%\n- هيمنة USDT: {usdt_d:.1f}%\n- الحالة: {status}"
    except:
        return "📊 **هيكل السوق:**\n- جاري تحديث بيانات الاستحواذ..."

async def get_trading_signals():
    try:
        # فحص العملات الأكثر نشاطاً فقط لتقليل الضغط
        markets = exchange.fetch_tickers(['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'])
        movers = []
        for symbol, ticker in markets.items():
            change = ticker['percentage']
            if change is not None and abs(change) > 1:
                movers.append((symbol, ticker))
        
        if not movers: return "🔎 لا توجد تذبذبات قوية حالياً."
        
        # اختيار العملة الأكثر حركة
        movers.sort(key=lambda x: abs(x[1]['percentage']), reverse=True)
        coin, data = movers[0]
        price = data['last']
        change = data['percentage']
        
        # منطق توصية مبدئي
        side = "LONG 🟢" if change > 0 else "SHORT 🔴"
        target = price * (1.03 if change > 0 else 0.97)
        stop = price * (0.97 if change > 0 else 1.03)
        
        return (f"🚨 **إشارة ذكية: {coin}**\n"
                f"📢 النوع: {side}\n"
                f"📈 التغير: {change:.1f}%\n"
                f"💰 السعر: {price}\n"
                f"🎯 الهدف: {target:.4f}\n"
                f"🛑 الستوب: {stop:.4f}\n"
                f"🔗 [شارت 5د](https://www.tradingview.com/chart/?symbol=BINANCE:{coin.replace('/', '')})")
    except:
        return "🔎 جاري مسح السيولة في Binance..."

async def main():
    print("🚀 انطلاق النظام بنسخة الإصلاح 1.2")
    while True:
        report = (
            f"🧠 **نظام الاستخبارات (AI - المرحلة 1.2)**\n"
            f"━━━━━━━━━━━━━━\n"
            f"{await analyze_market_liquidity()}\n"
            f"━━━━━━━━━━━━━━\n"
            f"📰 **تحليل الأخبار (Sentiment):**\n{await fetch_breaking_news()}\n"
            f"━━━━━━━━━━━━━━\n"
            f"{await get_trading_signals()}\n"
            f"━━━━━━━━━━━━━━\n"
            f"⚖️ إدارة المخاطر: 1% من المحفظة\n"
            f"⏰ التحديث التلقائي: كل 15 دقيقة"
        )
        try:
            await bot.send_message(chat_id=CHAT_ID, text=report, parse_mode='Markdown', disable_web_page_preview=True)
        except: pass
        await asyncio.sleep(900) # تقليل الوقت لـ 15 دقيقة ليكون "لحظي" أكثر

if __name__ == "__main__":
    asyncio.run(main())
