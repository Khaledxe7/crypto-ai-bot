import requests
import asyncio
import feedparser
from telegram import Bot

# --- الإعدادات ---
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
bot = Bot(token=TOKEN)

async def get_market_context():
    """تحليل الحالة العالمية (استحواذ، ذهب، دولار)"""
    try:
        # جلب الاستحواذ
        m_res = requests.get("https://api.coinlore.net/api/global/", timeout=10).json()[0]
        btcd = float(m_res['btc_d'])
        
        # تحليل الحالة الجيوسياسية والاقتصادية عبر الأخبار
        feed = feedparser.parse("https://cointelegraph.com/rss")
        news_report = ""
        risk_score = 0
        
        # كلمات مفتاحية للأزمات
        war_keywords = ['war', 'attack', 'fed', 'inflation', 'cpi', 'rates', 'sec', 'lawsuit']
        
        for entry in feed.entries[:3]:
            title = entry.title
            impact = "⚖️ عادي"
            if any(w in title.lower() for w in war_keywords):
                impact = "🔥 مرتفع (اقتصادي/سياسي)"
                risk_score += 1
            news_report += f"• {title} [{impact}]\n"
        
        status = "🔴 Risk-Off" if btcd > 56 or risk_score >= 2 else "🟢 Risk-On"
        return status, btcd, news_report
    except:
        return "⚠️ غير معروف", 0, "جاري تحديث الأخبار..."

async def scan_top_200_opportunities(btcd_val):
    """مسح أفضل 200 عملة واختيار 'القنبلة' الموقوتة (2-3%)"""
    try:
        # جلب قائمة الـ 200 الكبار
        top_200_res = requests.get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=200&page=1", timeout=10).json()
        top_200_symbols = [c['symbol'].upper() + "USDT" for c in top_200_res]
        
        # جلب بيانات بينانس للحركة اللحظية
        binance_res = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=10).json()
        
        opportunities = []
        for item in binance_res:
            symbol = item['symbol']
            if symbol in top_200_symbols:
                change = float(item['priceChangePercent'])
                volume = float(item['quoteVolume']) / 1e6
                
                # الشرط الذهبي: صعود 2-3.5% + سيولة > 15 مليون $ + استبعاد البيتكوين نفسه
                if 2.0 <= change <= 3.8 and volume > 15 and symbol != "BTCUSDT":
                    # تحليل فني سريع: هل السعر قريب من القمة اللحظية؟
                    last_price = float(item['lastPrice'])
                    high_price = float(item['highPrice'])
                    if last_price >= high_price * 0.98: # اختراق حقيقي
                        opportunities.append({
                            'symbol': symbol,
                            'price': last_price,
                            'change': change,
                            'vol': volume
                        })
        
        return sorted(opportunities, key=lambda x: x['vol'], reverse=True)[:2]
    except:
        return []

async def main():
    print("🧠 نظام الاستخبارات الشامل V2.0 قيد التشغيل...")
    while True:
        status, btcd, news = await get_market_context()
        signals = await scan_top_200_opportunities(btcd)
        
        # بناء التقرير الاحترافي
        report = (
            f"🤖 **AI Crypto Intelligence Brain**\n"
            f"━━━━━━━━━━━━━━\n"
            f"📊 **هيكل السوق العالمي:**\n"
            f"- الحالة العامة: {status}\n"
            f"- استحواذ البيتكوين: {btcd}%\n\n"
            f"🌍 **رادار الأخبار والجيوسياسة:**\n{news}\n"
            f"━━━━━━━━━━━━━━\n"
        )
        
        if signals:
            report += "🎯 **توصيات الاختراق المؤكدة (2-4%):**\n\n"
            for s in signals:
                report += (f"✅ **#{s['symbol']}**\n"
                           f"📈 الصعود: +{s['change']}%\n"
                           f"💰 السيولة: ${s['vol']:.1f}M (قوي)\n"
                           f"🎯 الهدف: {s['price']*1.03:.4f}\n"
                           f"🛑 الستوب: {s['price']*0.97:.4f}\n"
                           f"🔗 [شارت فريم 5د](https://www.tradingview.com/chart/?symbol=BINANCE:{s['symbol']})\n\n")
        else:
            report += "🔎 **حالة الرادار:** جاري فحص الـ 200 عملة.. لم يتم رصد اختراق مطابق للشروط حالياً.\n"
        
        report += (f"━━━━━━━━━━━━━━\n"
                   f"🛡️ **إدارة المخاطر:** التداول بـ 1% فقط.\n"
                   f"⏰ تحديث ذكي: كل 10 دقائق")

        try:
            await bot.send_message(chat_id=CHAT_ID, text=report, parse_mode='Markdown', disable_web_page_preview=True)
            print("✅ أرسل النظام تحليل الجد.")
        except:
            pass
            
        await asyncio.sleep(600)

if __name__ == "__main__":
    asyncio.run(main())
