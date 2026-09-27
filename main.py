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


def get_crypto_dict():
    """قاموس أسماء العملات الرقمية باللغة العربية"""
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
        "SUIUSDT": "سوي",
        "NEARUSDT": "نير بروتوكول",
        "LTCUSDT": "لايتكوين",
        "BCHUSDT": "بيتكوين كاش",
        "FETUSDT": "أليانس إيه آي",
        "RENDERUSDT": "رندر",
        "INJUSDT": "إنجيكتيف",
        "PEPEUSDT": "بيبي",
        "SHIBUSDT": "شيبا إينو",
        "WIFUSDT": "دوج ويف هات",
        "ENAUSDT": "إيثينا",
        "ARBUSDT": "أربتروم",
        "OPUSDT": "أوبتيميزم",
        "TIAUSDT": "سيليستيا",
        "SEIUSDT": "سي",
        "TAOUSDT": "بيتنسور",
        "UNIUSDT": "يوني سواب",
        "AAVEUSDT": "آفي",
        "FLOKIUSDT": "فلوكي",
        "BONKUSDT": "بونك"
    }


def fetch_crypto_from_binance():
    """جلب أسعار الكريبتو والحجم المالي مباشرة من Binance API لمنع الحظر نهائياً"""
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        df = pd.DataFrame(data)
        
        # تحويل الأعمدة إلى أرقام
        df["price"] = df["lastPrice"].astype(float)
        df["change"] = df["priceChangePercent"].astype(float)
        df["quoteVolume"] = df["quoteVolume"].astype(float)  # القيمة المالية بـ USDT
        df["volume"] = df["volume"].astype(float)           # عدد القطع
        df["ticker"] = df["symbol"]

        # الفلترة: الأزواج المقترنة بـ USDT فقط والارتفاع الإيجابي
        df_usdt = df[df["ticker"].str.endswith("USDT")].copy()
        
        # الترتيب حسب نسبة الارتفاع والصعود 24h
        df_sorted = df_usdt.sort_values(by="change", ascending=False)
        return df_sorted
    except Exception as e:
        print(f"⚠️ خطأ أثناء الاتصال بـ Binance API: {e}")
        return pd.DataFrame()


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

    print(f"⏰ [{now_time}] جاري إجراء الفحص المباشر عبر Binance API...")

    df = fetch_crypto_from_binance()
    crypto_dict = get_crypto_dict()

    if df.empty:
        print("❌ تعذر جلب البيانات.")
        send("⚠️ تعذر جلب البيانات من المصدر في الوقت الحالي.")
        return

    # التصفية أولاً بناءً على قائمة القاموس المعتمد
    filtered_df = df[df["ticker"].isin(crypto_dict.keys())]

    # في حال لم توجد نتائج كافية من القاموس، نأخذ أعلى العملات صعوداً في منصة بينانس بالكامل
    if filtered_df.empty or len(filtered_df) < 3:
        filtered_df = df.head(MAX_SHOWN)

    header = "🚨 <b>تحديث سوق الكريبتو (أعلى العملات زخماً وصعوداً)</b>\nℹ️ <i>المصدر: Binance Direct API</i>"
    blocks = []

    for idx, (_, row) in enumerate(filtered_df.head(MAX_SHOWN).iterrows(), 1):
        ticker = row["ticker"]
        arabic_name = escape_html(crypto_dict.get(ticker, ticker.replace("USDT", "")))
        tv_url = f"https://www.tradingview.com/chart/?symbol={EXCHANGE_NAME}:{ticker}"

        price = float(row["price"])
        change = float(row["change"])
        usdt_volume = float(row["quoteVolume"]) / 1_000_000  # الحجم المالي بـ ملايين الدولارات

        curr_count = counts.get(ticker, 0) + 1
        counts[ticker] = curr_count

        lvl = calculate_levels(price)

        lines = [
            f"🔥 <b>#{idx} {arabic_name} ({ticker})</b>",
            f"🚨 🛑 <b>[تنبيه رقم {curr_count}]</b>",
            f"💵 <b>السعر:</b> ${price:.4f} | <b>التغير 24h:</b> {change:+.2f}%",
            f"💰 <b>السيولة الماليّة:</b> ${usdt_volume:.2f}M USDT",
            f"📈 <b>الشارت:</b> <a href='{tv_url}'>فتح في TradingView</a>",
            f"🎯 <b>الأهداف:</b> ${lvl['t1']:.4f} -&gt; ${lvl['t2']:.4f} -&gt; ${lvl['t3']:.4f}",
            f"🛡️ <b>الدعم:</b> ${lvl['support']:.4f} | ⛔️ <b>الوقف:</b> ${lvl['stop_loss']:.4f}",
            "-----------------------------------"
        ]
        blocks.append("\n".join(lines))

    if blocks:
        msg_text = header + "\n\n" + "\n\n".join(blocks)
        send(msg_text)
        print(f"✅ تم إرسال {len(blocks)} عملة إلى التلغرام بنجاح.")

    save_seen(today, counts)


if __name__ == "__main__":
    main()
