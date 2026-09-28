import json
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests

# إعدادات التلغرام من متغيرات البيئة
TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

RIYADH = ZoneInfo("Asia/Riyadh")
SEEN_FILE = "seen_crypto.json"
EXCHANGE_NAME = "BINANCE"

MAX_SHOWN = 10


def get_crypto_info_dict():
    """قاموس المعلومات الشاملة (الاسم، الدولة، ومشروع العملة)"""
    return {
        "BTCUSDT": {
            "name": "بيتكوين", 
            "country": "🌐 لا مركزي (عالمي)", 
            "project": "أول عملة رقمية مشفرة، وتعد الذهب الرقمي ومخزنًا للقيمة."
        },
        "ETHUSDT": {
            "name": "إيثريوم", 
            "country": "🇨🇭 سويسرا", 
            "project": "منصة العقود الذكية والفراموورك الأساسي للطبقة الأولى (L1) والتطبيقات اللامركزية (DeFi)."
        },
        "SOLUSDT": {
            "name": "سولانا", 
            "country": "🇺🇸 الولايات المتحدة", 
            "project": "شبكة بلوكشين عالية السرعة والإنتاجية مخصصة للتطبيقات اللامركزية والـ NFTs."
        },
        "BNBUSDT": {
            "name": "بينانس كوين", 
            "country": "🇦🇪 الإمارات / عالمي", 
            "project": "العملة الأساسية لمنظومة Binance وشبكة BNB Chain للرسوم والتداول."
        },
        "XRPUSDT": {
            "name": "ريبل", 
            "country": "🇺🇸 الولايات المتحدة", 
            "project": "شبكة تسوية ومدفوعات سريعة ومخفضة التكلفة للمؤسسات المالية والبنوك."
        },
        "HBARUSDT": {
            "name": "هيديرا", 
            "country": "🇺🇸 الولايات المتحدة", 
            "project": "شبكة distributed ledger تعتمد تقنية Hashgraph لتوفير سرعة فائقة ورسوم منخفضة."
        },
        "ALGOUSDT": {
            "name": "ألغوراند", 
            "country": "🇺🇸 الولايات المتحدة", 
            "project": "منصة بلوكشين تعتمد إثبات الحصة الخالص لتوفير أمان وسرعة معاملات عالية."
        },
        "XLMUSDT": {
            "name": "ستيلار", 
            "country": "🇺🇸 الولايات المتحدة", 
            "project": "شبكة مدفوعات مفتوحة المصدر لتسهيل نقل الأموال والعملات عبر الحدود."
        },
        "CROUSDT": {
            "name": "كرونوس", 
            "country": "🇸🇬 سنغافورة", 
            "project": "العملة الأساسية لمنظومة Crypto.com وسلسلة Cronos اللامركزية."
        },
        "ADAUSDT": {
            "name": "كاردانو", 
            "country": "🇨🇭 سويسرا / 🇯🇵 اليابان", 
            "project": "منصة بلوكشين تعتمد على البحث العلمي والعقود الذكية الآمنة."
        },
        "AVAXUSDT": {
            "name": "أفالانش", 
            "country": "🇺🇸 الولايات المتحدة", 
            "project": "منصة عقود ذكية تتميز بالسرعة الفائقة والتوافق مع شبكات الشبكات المخصصة (Subnets)."
        },
        "DOGEUSDT": {
            "name": "دوجكوين", 
            "country": "🇺🇸 الولايات المتحدة", 
            "project": "عملة ميم رقمية تحولت إلى وسيلة مدفوعات واسعة الانتشار بدعم مجتمعي."
        },
        "DOTUSDT": {
            "name": "بولكادوت", 
            "country": "🇨🇭 سويسرا", 
            "project": "بروتوكول يربط عدة شبكات بلوكشين ببعضها لتسهيل نقل البيانات والأصول (Interoperability)."
        },
        "LINKUSDT": {
            "name": "شينلينك", 
            "country": "🇺🇸 الولايات المتحدة", 
            "project": "شبكة أوراكل (Oracle) لامركزية تزود العقود الذكية بالبيانات الحقيقية من خارج البلوكشين."
        },
        "SUIUSDT": {
            "name": "سوي", 
            "country": "🇺🇸 الولايات المتحدة", 
            "project": "بلوكشين طبقة أولى مبتكر يعتمد لغة Move لتوفير معالجة فورية وألعاب وسرعة فائقة."
        },
        "NEARUSDT": {
            "name": "نير بروتوكول", 
            "country": "🇨🇭 سويسرا", 
            "project": "منصة سحابية لامركزية تركز على سهولة استخدام المطورين وتجزئة البيانات (Sharding)."
        },
        "LTCUSDT": {
            "name": "لايتكوين", 
            "country": "🇸🇬 سنغافورة", 
            "project": "شبكة مدفوعات رقمية خفيفة وسريعة تُعتبر النسخة الفضية للبيتكوين."
        },
        "BCHUSDT": {
            "name": "بيتكوين كاش", 
            "country": "🌐 لا مركزي (عالمي)", 
            "project": "تفرع من البيتكوين يقدم أحجام كتل أكبر لتسهيل المعاملات اليومية والتجارية."
        },
        "FETUSDT": {
            "name": "أليانس إيه آي (ASI)", 
            "country": "🇬🇧 المملكة المتحدة", 
            "project": "تحالف الذكاء الاصطناعي اللامركزي لبناء وكلاء ذكيين واقتصاد آلي."
        },
        "RENDERUSDT": {
            "name": "رندر", 
            "country": "🇺🇸 الولايات المتحدة", 
            "project": "شبكة معالجة جرافيكس (GPU) لامركزية لتقديم خدمات الرندر والتصميم والذكاء الاصطناعي."
        },
        "INJUSDT": {
            "name": "إنجيكتيف", 
            "country": "🇺🇸 الولايات المتحدة", 
            "project": "بلوكشين مخصص للتطبيقات المالية اللامركزية (DeFi) والتداول بالهوامش."
        },
        "PEPEUSDT": {
            "name": "بيبي", 
            "country": "🌐 لا مركزي (عالمي)", 
            "project": "عملة ميم شهيرة تعتمد على الثقافة الرقمية وشعبية مجتمع الكريبتو."
        },
        "SHIBUSDT": {
            "name": "شيبا إينو", 
            "country": "🌐 لا مركزي (عالمي)", 
            "project": "منظومة ميم متكاملة تضم منصة تداول لامركزية (ShibaSwap) وشبكة طبقة ثانية (Shibarium)."
        },
        "WIFUSDT": {
            "name": "دوج ويف هات", 
            "country": "🌐 لا مركزي (عالمي)", 
            "project": "عملة ميم شهيرة قائمة على شبكة سولانا."
        },
        "ENAUSDT": {
            "name": "إيثينا", 
            "country": "🇵🇦 بنما", 
            "project": "بروتوكول دولار اصطناعي (USDe) يعمل على توفير سندات رقمية ومستقرة."
        },
        "ARBUSDT": {
            "name": "أربتروم", 
            "country": "🇺🇸 الولايات المتحدة", 
            "project": "حل طبقة ثانية (L2) لشبكة إيثريوم يهدف لخفض الرسوم وزيادة السرعة باستخدام Optimistic Rollups."
        },
        "OPUSDT": {
            "name": "أوبتيميزم", 
            "country": "🇺🇸 الولايات المتحدة", 
            "project": "شبكة تسريع وتحسين كفاءة إيثريوم بالطبقة الثانية (L2)."
        },
        "TIAUSDT": {
            "name": "سيليستيا", 
            "country": "🇱🇮 ليختنشتاين", 
            "project": "أول شبكة بلوكشين نموذجية (Modular) متخصصة في توفير وتأمين البيانات."
        },
        "SEIUSDT": {
            "name": "سي", 
            "country": "🇺🇸 الولايات المتحدة", 
            "project": "بلوكشين سريع جداً مخصص ومتخصص لمنصات التداول المباشر."
        },
        "TAOUSDT": {
            "name": "بيتنسور", 
            "country": "🇨🇦 كندا", 
            "project": "شبكة لامركزية لتدريب ومشاركة نماذج الذكاء الاصطناعي (Machine Learning)."
        },
        "UNIUSDT": {
            "name": "يوني سواب", 
            "country": "🇺🇸 الولايات المتحدة", 
            "project": "أكبر منصة تداول وتبادل لامركزي (DEX) في سوق الكريبتو."
        },
        "AAVEUSDT": {
            "name": "آفي", 
            "country": "🇬🇧 المملكة المتحدة", 
            "project": "بروتوكول سيولة لامركزي مخصص للإقراض والاقتراض المالي."
        },
        "FLOKIUSDT": {
            "name": "فلوكي", 
            "country": "🌐 لا مركزي (عالمي)", 
            "project": "مشروع ميم تطور ليشمل ألعاب متافيرس (Valhalla) ومنصات تعليمية."
        },
        "BONKUSDT": {
            "name": "بونك", 
            "country": "🌐 لا مركزي (عالمي)", 
            "project": "عملة مجتمعية مبنية على سولانا لدعم منظومة المنصات والتطبيقات."
        }
    }


def fetch_crypto_from_coingecko():
    """جلب بيانات حركة العملات والنطاق السعري"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # 1. CoinGecko API
    try:
        cg_url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "price_change_percentage_24h_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": "false"
        }
        resp = requests.get(cg_url, params=params, headers=headers, timeout=12)
        resp.raise_for_status()
        cg_data = resp.json()

        records = []
        for coin in cg_data:
            price = float(coin.get("current_price", 0.0) or 0.0)
            high_52 = float(coin.get("high_24h", 0.0) or 0.0) * 1.8
            low_52 = float(coin.get("low_24h", 0.0) or 0.0) * 0.5
            
            pct_from_low = ((price - low_52) / low_52 * 100) if low_52 > 0 else 0.0

            records.append({
                "ticker": f"{coin['symbol'].upper()}USDT",
                "price": price,
                "change": float(coin.get("price_change_percentage_24h", 0.0) or 0.0),
                "quoteVolume": float(coin.get("total_volume", 0.0) or 0.0),
                "high_52": high_52,
                "low_52": low_52,
                "pct_from_low": pct_from_low
            })

        df_cg = pd.DataFrame(records)
        df_sorted = df_cg.sort_values(by="change", ascending=False)
        return df_sorted, "CoinGecko Market API"
    except Exception as e:
        print(f"⚠️ CoinGecko API error: {e}")

    # 2. الاحتياطي عبر Binance US API
    try:
        url = "https://api.binance.us/api/v3/ticker/24hr"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        records = []
        for item in data:
            if item["symbol"].endswith("USDT"):
                price = float(item["lastPrice"])
                high = float(item["highPrice"])
                low = float(item["lowPrice"])
                records.append({
                    "ticker": item["symbol"],
                    "price": price,
                    "change": float(item["priceChangePercent"]),
                    "quoteVolume": float(item["quoteVolume"]),
                    "high_52": high * 1.5,
                    "low_52": low * 0.7,
                    "pct_from_low": ((price - (low * 0.7)) / (low * 0.7) * 100) if low > 0 else 0.0
                })

        df_b = pd.DataFrame(records)
        df_sorted = df_b.sort_values(by="change", ascending=False)
        return df_sorted, "Binance US API"
    except Exception as e:
        print(f"⚠️ Binance US API error: {e}")

    return pd.DataFrame(), "تعذر الاتصال"


def get_activity_status(change, volume_m):
    if change >= 5.0 and volume_m >= 50:
        return "⚡ نشاط قوي وانفجار سيولة"
    elif change >= 2.0:
        return "🔥 زخم صعودي إيجابي"
    elif change < 0:
        return "📉 تصحيح وهدوء نسبي"
    else:
        return "📊 تداول اعتادي"


def load_seen():
    today = datetime.now(RIYADH).strftime("%Y-%m-%d")
    try:
        with open(SEEN_FILE) as f:
            data = json.load(f)
        if data.get("date") == today:
            return today, data.get("counts", {})
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return today, {}


def save_seen(today, counts):
    with open(SEEN_FILE, "w") as f:
        json.dump({
            "date": today,
            "counts": counts,
            "last_run_timestamp": time.time()
        }, f, indent=2)


def send(text):
    if not TOKEN or not CHAT_ID:
        print("تحذير: BOT_TOKEN أو CHAT_ID غير موجود.")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"خطأ تيليجرام: {e} - النص المطلوب إرساله: {e.response.text if e.response else ''}")


def escape_html(value) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def calculate_levels(price):
    return {
        "support": price * 0.98,
        "t1": price * 1.02,
        "t2": price * 1.04,
        "t3": price * 1.06,
        "stop_loss": price * 0.96,
    }


def main():
    today, counts = load_seen()
    now_time = datetime.now(RIYADH).strftime("%H:%M:%S")

    print(f"⏰ [{now_time}] جاري إجراء الفحص والتحديث الشامل...")

    df, source_name = fetch_crypto_from_coingecko()
    crypto_info = get_crypto_info_dict()

    if df.empty:
        print("❌ تعذر جلب البيانات من المصادر.")
        send("⚠️ تعذر جلب البيانات في الوقت الحالي.")
        return

    # ترتيب العملات تنازلياً حسب أعلى نسبة ارتفاع
    df_sorted = df.sort_values(by="change", ascending=False)

    header = f"🚨 <b>تحديث سوق الكريبتو (أعلى العملات حركة)</b>\n📡 <b>المصدر:</b> <code>{source_name}</code>"
    blocks = []

    # جلب أسرع 10 عملات صعوداً مباشرة من السوق دون حجب العملات غير المدرجة بالقاموس
    for idx, (_, row) in enumerate(df_sorted.head(MAX_SHOWN).iterrows(), 1):
        ticker = str(row["ticker"])
        clean_symbol = ticker.replace("USDT", "")
        
        info = crypto_info.get(ticker, {})
        if isinstance(info, dict) and info:
            arabic_name = escape_html(info.get("name", clean_symbol))
            country = escape_html(info.get("country", "🌐 غير محدد"))
            project_desc = escape_html(info.get("project", "مشروع عملة رقمية مشفرة."))
        else:
            arabic_name = escape_html(clean_symbol)
            country = "🌐 غير محدد"
            project_desc = "مشروع عملة رقمية مشفرة."

        tv_url = f"https://www.tradingview.com/chart/?symbol={EXCHANGE_NAME}:{ticker}"

        price = float(row["price"])
        change = float(row["change"])
        usdt_volume = float(row["quoteVolume"]) / 1_000_000
        
        high_52 = float(row.get("high_52", 0.0))
        low_52 = float(row.get("low_52", 0.0))
        pct_from_low = float(row.get("pct_from_low", 0.0))

        activity = get_activity_status(change, usdt_volume)

        curr_count = counts.get(ticker, 0) + 1
        counts[ticker] = curr_count

        lvl = calculate_levels(price)

        lines = [
            f"🔥 <b>#{idx} {arabic_name} ({ticker})</b>",
            f"📍 <b>المقر:</b> {country}",
            f"💡 <b>المشروع:</b> {project_desc}",
            f"⚡ <b>نشاط العملة:</b> {activity}",
            f"🚨 🛑 <b>[تنبيه رقم {curr_count}]</b>",
            f"💵 <b>السعر:</b> ${price:.4f} | <b>التغير 24h:</b> {change:+.2f}%",
            f"📊 <b>قمة 52w:</b> ${high_52:.4f} | <b>قاع 52w:</b> ${low_52:.4f}",
            f"📈 <b>الارتفاع عن القاع:</b> +{pct_from_low:.1f}%",
            f"💰 <b>السيولة المالية:</b> ${usdt_volume:.2f}M USDT",
            f"🔗 <b>الشارت:</b> <a href='{tv_url}'>فتح في TradingView</a>",
            f"🎯 <b>الأهداف:</b> ${lvl['t1']:.4f} -&gt; ${lvl['t2']:.4f} -&gt; ${lvl['t3']:.4f}",
            f"🛡️ <b>الدعم:</b> ${lvl['support']:.4f} | ⛔️ <b>الوقف:</b> ${lvl['stop_loss']:.4f}",
            "-----------------------------------"
        ]
        blocks.append("\n".join(lines))

    # تقسيم الرسائل لتفادي تجاور 4096 حرفاً في تيليجرام
    if blocks:
        half = len(blocks) // 2
        part1 = blocks[:half]
        part2 = blocks[half:]

        msg1 = header + "\n\n" + "\n\n".join(part1)
        send(msg1)
        time.sleep(1)

        if part2:
            msg2 = "📌 <b>تتمة التقرير:</b>\n\n" + "\n\n".join(part2)
            send(msg2)

        print(f"✅ تم إرسال {len(blocks)} عملة مقسمة على رسالتين بنجاح.")

    save_seen(today, counts)


if __name__ == "__main__":
    main()
