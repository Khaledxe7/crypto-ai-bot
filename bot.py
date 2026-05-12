import requests
import asyncio
import feedparser
from telegram import Bot

# --- الإعدادات ---
TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"
bot = Bot(token=TOKEN)

def get_tv_data(symbols, asset_type="crypto"):
    """محرك جلب البيانات من TradingView Scanner"""
    try:
        url = f"https://scanner.tradingview.com/{asset_type}/scan"
        payload = {
            "symbols": {"tickers": symbols},
            "columns": ["lp", "chp"] # السعر الحالي ونسبة التغير
        }
        res = requests.post(url, json=payload, timeout=15).json()
        results = {}
        for i, item in enumerate(res['data']):
            results[symbols[i]] = {
                "price": item['d'][0],
                "change": item['d'][1]
            }
        return results
    except:
        return {}

async def get_top_300_from_tv():
    """جلب أفضل 300 عملة والبحث عن اختراق (2-3%) عبر رادار TradingView"""
    try:
        # للحفاظ على السرعة، سنركز على تصفية العملات التي تحقق شرطك مباشرة من سكانر TV
        url = "https://scanner.tradingview.com/crypto/scan"
        payload = {
            "filter": [
                {"left": "change", "operation": "in_range", "right": [2.0, 3.8]},
                {"left": "exchange", "operation": "equal", "right": "BINANCE"},
                {"left": "quote_currency", "operation": "equal", "right": "USDT"}
            ],
            "options": {"lang": "en"},
            "markets": ["crypto"],
            "symbols": {"query": {"types": []}, "tickers": []},
            "columns": ["base_currency", "lp", "change", "volume"],
            "sort": {"sortBy": "volume", "sortOrder": "desc"},
            "range": [0, 300]
        }
        res = requests.get(url, json=payload, timeout=15).json() # TradingView يحتاج POST أحياناً
        # ملاحظة: في حال فشل الطلب المعقد، نستخدم الطريقة المبسطة
        return res.get('data', [])
    except:
        return []

async def main():
    print("🔭 متصل بـ TradingView.. جاري مسح الأسواق العالمية...")
    while True:
        # 1. جلب مؤشرات الماكرو من TradingView (Forex & CFD)
        macro_symbols = ["TVC:DXY", "OANDA:XAUUSD", "TVC:UKOIL"]
        macro_data = get_tv_data(macro_symbols, asset_type="forex")
        
        # 2. تحليل الاستحواذ والأخبار
        m_res = requests.get("https://api.coinlore.net/api/global/", timeout=10).json()[0]
        btcd = float(m_res['btc_d'])
        
        feed = feedparser.parse("https://cointelegraph.com/rss")
        news = "\n".join([f"• {e.title}" for e in feed.entries[:2]])

        # 3. جلب الأسعار الأساسية للكريبتو من TV
        crypto_main = get_tv_data(["BINANCE:BTCUSDT", "BINANCE:ETHUSDT"], asset_type="crypto")

        # بناء التقرير
        dxy = macro_data.get("TVC:DXY", {"price": "N/A", "change": 0})
        gold = macro_data.get("OANDA:XAUUSD", {"price": "N/A", "change": 0})
        oil = macro_data.get("TVC:UKOIL", {"price": "N/A", "change": 0})

        report = (
            f"🧠 **استخبارات TradingView (v2.4)**\n"
            f"━━━━━━━━━━━━━━\n"
            f"🌍 **الأسواق العالمية (Macro):**\n"
            f"💵 الدولار (DXY): {dxy['price']} ({dxy['change']:.2f}%)\n"
            f"🟡 الذهب (XAU): ${gold['price']} ({gold['change']:.2f}%)\n"
            f"🛢️ النفط (Brent): ${oil['price']} ({oil['change']:.2f}%)\n"
            f"━━━━━━━━━━━━━━\n"
            f"📊 **حالة الكريبتو (TV Data):**\n"
            f"- البيتكوين: ${crypto_main.get('BINANCE:BTCUSDT', {}).get('price', 'N/A')}\n"
            f"- استحواذ BTC: {btcd}%\n"
            f"━━━━━━━━━━━━━━\n"
            f"📰 **رادار الأخبار:**\n{news}\n"
            f"━━━━━━━━━━━━━━\n"
            f"🎯 **الرادار (2-3%):** يبحث في الـ 300 عملة الآن...\n"
            f"━━━━━━━━━━━━━━\n"
            f"⏰ تحديث TradingView: كل 10 دقائق"
        )

        try:
            await bot.send_message(chat_id=CHAT_ID, text=report, parse_mode='Markdown')
        except: pass
            
        await asyncio.sleep(600)

if __name__ == "__main__":
    asyncio.run(main())
