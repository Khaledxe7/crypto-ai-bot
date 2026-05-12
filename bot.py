import requests
import asyncio
import ccxt
from telegram import Bot

# --- الإعدادات ---
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
bot = Bot(token=TOKEN)

# إعداد Binance مع تجنب مشاكل الاتصال
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

async def fetch_breaking_news():
    try:
        # استخدام مصدر بديل ومباشر للأخبار
        url = "https://cryptopanic.com/api/v1/posts/?public=true"
        res = requests.get(url, timeout=15).json()
        news_items = []
        for post in res.get('results', [])[:3]:
            news_items.append(f"• {post['title']}")
        return "\n".join(news_items) if news_items else "لا توجد أخبار حالياً."
    except Exception as e:
        return f"⚠️ عطل مؤقت في جلب الأخبار."

async def analyze_market_liquidity():
    try:
        data = requests.get("https://api.coingecko.com/api/v3/global", timeout=10).json()['data']
        btc_d = data['market_cap_percentage']['btc']
        usdt_d = data['market_cap_percentage'].get('usdt', 6.5) # قيمة افتراضية إذا لم تتوفر
        
        status = "🟢 Risk-On" if usdt_d < 4.5 else "🔴 Risk-Off"
        return f"📊 **سيولة السوق:**\n- استحواذ BTC: {btc_d:.1f}%\n- هيمنة USDT: {usdt_d:.1f}%\n- الوضع الحالي: {status}"
    except:
        return "⚠️ فشل تحليل السيولة الكلية."

async def get_trading_signals():
    try:
        # جلب الأسعار لافضل 20 عملة من حيث الحجم
        tickers = exchange.fetch_tickers()
        # نفلتر العملات الصاعدة التي فيها سيولة
        movers = []
        for symbol, ticker in tickers.items():
            if '/USDT' in symbol and ticker['percentage'] is not None:
                if ticker['percentage'] > 3: # صعود أكثر من 3%
                    movers.append((symbol, ticker))
        
        if not movers:
            return "🔎 السوق مستقر، لا توجد عملات مندفعة سيولياً."
        
        # ترتيب حسب الأعلى صعوداً
        movers.sort(key=lambda x: x[1]['percentage'], reverse=True)
        top_coin, data = movers[0]
        
        price = data['last']
        change = data['percentage']
        target = price * 1.03
        stop = price * 0.97
        
        return (f"🚀 **إشارة سيولة: {top_coin}**\n"
                f"📈 التغير: +{change:.1f}%\n"
                f"💰 السعر: {price}\n"
                f"🎯 الهدف (3%): {target:.4f}\n"
                f"🛑 الستوب: {stop:.4f}\n"
                f"🔗 [شارت 5د](https://www.tradingview.com/chart/?symbol=BINANCE:{top_coin.replace('/', '')})")
    except Exception as e:
        print(f"Error in trading engine: {e}")
        return "⚠️ محرك التداول قيد التحديث."

async def main():
    print("🛠️ تشغيل النظام المطور...")
    while True:
        liquidity = await analyze_market_liquidity()
        news = await fetch_breaking_news()
        signal = await get_trading_signals()
        
        report = (
            f"🧠 **نظام الاستخبارات (المرحلة 1.1)**\n"
            f"━━━━━━━━━━━━━━\n"
            f"{liquidity}\n"
            f"━━━━━━━━━━━━━━\n"
            f"📰 **آخر المستجدات:**\n{news}\n"
            f"━━━━━━━━━━━━━━\n"
            f"{signal}\n"
            f"━━━━━━━━━━━━━━\n"
            f"⚡ يتم الفحص كل 30 دقيقة"
        )
        
        try:
            await bot.send_message(chat_id=CHAT_ID, text=report, parse_mode='Markdown', disable_web_page_preview=True)
        except Exception as e:
            print(f"Send Error: {e}")
            
        await asyncio.sleep(1800) # فحص كل 30 دقيقة لاقتناص الفرص أسرع

if __name__ == "__main__":
    asyncio.run(main())
