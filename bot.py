import requests
import asyncio
import ccxt
from telegram import Bot

# --- الإعدادات الأساسية ---
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
bot = Bot(token=TOKEN)
exchange = ccxt.binance()

# 1. وظيفة جلب الأخبار العاجلة
async def fetch_breaking_news():
    try:
        url = "https://cryptopanic.com/api/v1/posts/?public=true&filter=important"
        res = requests.get(url, timeout=10).json()
        news_items = []
        for post in res['results'][:2]: # نأخذ أهم خبرين فقط للتبسيط الآن
            news_items.append(f"• {post['title']}")
        return "\n".join(news_items) if news_items else "لا توجد أخبار عاجلة حالياً."
    except:
        return "⚠️ تعذر الاتصال بمصدر الأخبار."

# 2. وظيفة تحليل سيولة السوق (BTC.D & TOTAL3)
async def analyze_market_liquidity():
    try:
        data = requests.get("https://api.coingecko.com/api/v3/global").json()['data']
        btc_d = data['market_cap_percentage']['btc']
        usdt_d = data['market_cap_percentage'].get('usdt', 0)
        total_mcap = data['total_market_cap']['usd'] / 1e12
        
        # تحليل بسيط للوضع
        status = "🟢 Risk-On (دخول سيولة)" if usdt_d < 4.5 else "🔴 Risk-Off (هروب للكاش)"
        return f"📊 **سيولة السوق:**\n- استحواذ BTC: {btc_d:.1f}%\n- هيمنة USDT: {usdt_d:.1f}%\n- الوضع: {status}"
    except:
        return "⚠️ فشل تحليل السيولة."

# 3. وظيفة فحص الفرص (السكالبينج)
async def get_trading_signals():
    try:
        tickers = exchange.fetch_tickers()
        # نبحث عن عملة صاعدة بفوليوم جيد
        movers = [s for s in tickers if '/USDT' in s and tickers[s]['percentage'] > 5]
        if not movers: return "🔎 لا توجد فرص واضحة حالياً."
        
        best_coin = movers[0] # نأخذ أقوى عملة صاعدة
        price = tickers[best_coin]['last']
        target = price * 1.03 # هدف 3%
        stop = price * 0.97   # ستوب 3%
        
        return (f"🚀 **إشارة تداول مقترحة: {best_coin}**\n"
                f"💰 السعر الحالي: {price}\n"
                f"🎯 الهدف: {target:.4f}\n"
                f"🛑 الستوب: {stop:.4f}")
    except:
        return "⚠️ فشل محرك التداول."

async def main():
    print("🛠️ جاري تشغيل المرحلة الأولى من النظام...")
    while True:
        # جمع البيانات من كل المحركات
        news = await fetch_breaking_news()
        liquidity = await analyze_market_liquidity()
        signal = await get_trading_signals()
        
        report = (
            f"🧠 **نظام الاستخبارات (المرحلة 1)**\n"
            f"━━━━━━━━━━━━━━\n"
            f"{liquidity}\n"
            f"━━━━━━━━━━━━━━\n"
            f"📰 **أهم الأخبار:**\n{news}\n"
            f"━━━━━━━━━━━━━━\n"
            f"{signal}\n"
            f"━━━━━━━━━━━━━━\n"
            f"⏰ التحديث القادم بعد ساعة"
        )
        
        try:
            await bot.send_message(chat_id=CHAT_ID, text=report, parse_mode='Markdown')
            print("✅ أرسل النظام تقريره الأول.")
        except Exception as e:
            print(f"❌ خطأ: {e}")
            
        await asyncio.sleep(3600) # تحديث كل ساعة

if __name__ == "__main__":
    asyncio.run(main())
