import json
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from tradingview_screener import Query, col

# استيراد TvDatafeed بحذر
tv = None
try:
    from tvdatafeed import TvDatafeed, Interval
    tv = TvDatafeed()
except Exception as e:
    print(f"⚠️ تحذير: لم يتم الاتصال بـ TvDatafeed: {e}")

# إعدادات التلغرام من متغيرات البيئة
TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

RIYADH = ZoneInfo("Asia/Riyadh")
SEEN_FILE = "seen_crypto.json"
EXCHANGE_NAME = "BINANCE"

MAX_SHOWN = 15


def get_crypto_dict():
    """قاموس العملات الرقمية"""
    return {
        "BTCUSDT": "بيتكوين",
        "ETHUSDT": "إيثريوم",
        "SOLUSDT": "سولانا",
        "BNBUSDT": "بينانس كوين",
        "XRPUSDT": "ريبل",
        "ADAUSDT": "كاردانو",
        "AVAXUSDT": "أفالانش",
        "DOGEUSDT": "دوجكوين",
        "DOTUSDT": "بولكادوت",
        "LINKUSDT": "شينلينك",
        "TONUSDT": "تون كوين",
        "SUIUSDT": "سوي",
        "APTUSDT": "أبتوس",
        "NEARUSDT": "نير بروتوكول",
        "LTCUSDT": "لايتكوين",
        "BCHUSDT": "بيتكوين كاش",
        "ETCUSDT": "إيثريوم كلاسيك",
        "ATOMUSDT": "كوزموس",
        "ICPUSDT": "إنترنت كومبيوتر",
        "TRXUSDT": "ترون",
        "XLMUSDT": "ستيلار",
        "FILUSDT": "فايلكوين",
        "HBARUSDT": "هيديرا",
        "ARBUSDT": "أربتروم",
        "OPUSDT": "أوبتيميزم",
        "TIAUSDT": "سيليستيا",
        "SEIUSDT": "سي",
        "FETUSDT": "أليانس إيه آي (ASI)",
        "RENDERUSDT": "رندر",
        "INJUSDT": "إنجيكتيف",
        "WLDUSDT": "ورلد كوين",
        "TAOUSDT": "بيتنسور",
        "UNIUSDT": "يوني سواب",
        "AAVEUSDT": "آفي",
        "PEPEUSDT": "بيبي",
        "SHIBUSDT": "شيبا إينو",
        "WIFUSDT": "دوج ويف هات",
        "FLOKIUSDT": "فلوكي",
        "BONKUSDT": "بونك",
        "JUPUSDT": "جوبيتر",
        "ENAUSDT": "إيثينا"
    }


def screens():
    """فلاتر المسح المقبولة من TradingView"""
    
    # 1. حركة إيجابية وصعود
    positive_momentum = [
        col("close") > 0,
        col("change") >= 0.1,
    ]

    # 2. انطلاق وزخم
    breakout_momentum = [
        col("close") > 0,
        col("change") >= 0.5,
    ]

    extra = ["close", "change", "volume"]
    return extra, "change", {
        "🚀 1️⃣ العملات ذات الزخم الإيجابي": positive_momentum,
        "🔥 2️⃣ العملات الأكثر ارتفاعًا وتحركًا": breakout_momentum,
    }


def run_screen(filters, columns, sort_col):
    """استعلام مباشر وشامل لجميع عملات الكريبتو من تريادنج فيو"""
    try:
        query = (
            Query()
            .set_markets("crypto")
            .select("name", "close", "change", "volume", "relative_volume_10d_calc", "RSI")
            .where(*filters)
            .order_by(sort_col, ascending=False)
            .limit(100)
        )
        _, df = query.get_scanner_data()
        
        if df is not None and not df.empty:
            # تنظيف رمز العملة ليتطابق مع القاموس
            df["clean_ticker"] = df["name"].astype(str).str.replace(f"{EXCHANGE_NAME}:", "").str.replace("USDT", "USDT")
            return df
    except Exception as e:
        print(f"خطأ في الاستعلام من TradingView: {e}")

    return None


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
        print(f"خطأ تيليجرام: {e}")


def escape_html(value) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def calculate_levels(price):
    r1 = price * 1.02
    r2 = price * 1.04
    r3 = price * 1.06
    support = price * 0.98
    stop_loss = price * 0.96

    return {
        "support": support,
        "t1": r1,
        "t2": r2,
        "t3": r3,
        "stop_loss": stop_loss,
    }


def main():
    today, counts = load_seen()
    now_time = datetime.now(RIYADH).strftime("%H:%M:%S")

    print(f"⏰ [{now_time}] جاري إجراء الفحص الشامل لعملات الكريبتو...")

    extra, sort_col, defs = screens()
    crypto_dict = get_crypto_dict()

    total_alerts_sent = 0

    for label, filters in defs.items():
        df = run_screen(filters, extra, sort_col)

        if df is None or df.empty:
            continue

        # الفلترة لتصفية عملات القاموس المعتمدة فقط
        df = df[df["clean_ticker"].isin(crypto_dict.keys())]

        if df.empty:
            continue

        header = f"🚨 <b>{label}</b>"
        blocks = []

        for idx, (_, row) in enumerate(df.head(MAX_SHOWN).iterrows(), 1):
            ticker = row["clean_ticker"]
            arabic_name = escape_html(crypto_dict.get(ticker, ticker))
            tv_url = f"https://www.tradingview.com/chart/?symbol={EXCHANGE_NAME}:{ticker}"

            price = float(row.get("close", 0.0))
            change = float(row.get("change", 0.0))
            volume = float(row.get("volume", 0.0))
            rsi = float(row.get("RSI", 0.0)) if not pd.isna(row.get("RSI")) else 0.0

            curr_count = counts.get(ticker, 0) + 1
            counts[ticker] = curr_count

            lvl = calculate_levels(price)

            lines = [
                f"🔥 <b>#{idx} {arabic_name} ({ticker})</b>",
                f"🚨 🛑 <b>[تنبيه رقم {curr_count}]</b>",
                f"💵 <b>السعر:</b> ${price:.4f} | <b>التغير:</b> +{change:.2f}%",
                f"📊 <b>الحجم (Vol):</b> {int(volume):,}" + (f" | <b>RSI:</b> {rsi:.1f}" if rsi > 0 else ""),
                f"📈 <b>الشارت:</b> <a href='{tv_url}'>فتح في TradingView</a>",
                f"🎯 <b>الأهداف:</b> ${lvl['t1']:.4f} -&gt; ${lvl['t2']:.4f} -&gt; ${lvl['t3']:.4f}",
                f"🛡️ <b>الدعم:</b> ${lvl['support']:.4f} | ⛔️ <b>الوقف:</b> ${lvl['stop_loss']:.4f}",
                "-----------------------------------"
            ]
            blocks.append("\n".join(lines))

        if blocks:
            msg_text = header + "\n\n" + "\n\n".join(blocks)
            send(msg_text)
            total_alerts_sent += len(blocks)

    save_seen(today, counts)
    print(f"📊 إجمالي العملات التي تم إرسالها: {total_alerts_sent}")


if __name__ == "__main__":
    now_str = datetime.now(RIYADH).strftime("%Y-%m-%d %H:%M:%S")
    print(f"🚀 [{now_str}] بدء جولة فحص الكريبتو...")

    # إرسال رسالة التنبيه عند بدء الفحص
    send(f"🤖 <b>بدء جولة فحص العملات الرقمية:</b> {now_str}")

    try:
        main()
        print("✅ اكتملت جولة الفحص بنجاح.")
    except Exception as e:
        print(f"⚠️ حدث خطأ أثناء تنفيذ الجولة: {e}")
        sys.exit(1)
