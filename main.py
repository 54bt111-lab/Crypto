import json
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from tradingview_screener import Query, col

# إعدادات التلغرام من متغيرات البيئة
TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

RIYADH = ZoneInfo("Asia/Riyadh")
SEEN_FILE = "seen_crypto.json"
EXCHANGE_NAME = "BINANCE"

MAX_SHOWN = 10


def get_crypto_dict():
    """قاموس العملات الرقمية المعتمدة"""
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
        "ENAUSDT": "إيثينا"
    }


def fetch_crypto_data():
    """استعلام مستقر ومباشر دون استخدام أعمدة غير مدعومة"""
    
    # 1. الاستعلام الأساسي: أعلى العملات صعوداً مع حجم تداول مقبول
    try:
        q1 = (
            Query()
            .set_markets("crypto")
            .select("name", "close", "change", "volume")
            .where(
                col("volume") >= 10000,
                col("change") >= 0.1
            )
            .order_by("change", ascending=False)
            .limit(100)
        )
        _, df1 = q1.get_scanner_data()
        if df1 is not None and not df1.empty:
            df1["ticker"] = df1["name"].astype(str).str.replace(f"{EXCHANGE_NAME}:", "").str.strip()
            return df1, "🔥 عملات ذات زخَم إيجابي وصعود متواصل"
    except Exception as e:
        print(f"⚠️ خطأ في الاستعلام الأول: {e}")

    # 2. الاستعلام الاحتياطي: ترتيب العملات بحسب الحجم المالي والحركة في السوق
    try:
        q2 = (
            Query()
            .set_markets("crypto")
            .select("name", "close", "change", "volume")
            .order_by("volume", ascending=False)
            .limit(100)
        )
        _, df2 = q2.get_scanner_data()
        if df2 is not None and not df2.empty:
            df2["ticker"] = df2["name"].astype(str).str.replace(f"{EXCHANGE_NAME}:", "").str.strip()
            return df2, "📊 أعلى العملات تداولاً وحركة في السوق"
    except Exception as e:
        print(f"⚠️ خطأ في الاستعلام الثاني: {e}")

    return pd.DataFrame(), "تعذر الاتصال"


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

    print(f"⏰ [{now_time}] جاري إجراء الفحص الشامل لعملات الكريبتو...")

    df, condition_info = fetch_crypto_data()
    crypto_dict = get_crypto_dict()

    if df.empty:
        print("❌ لم يتم العثور على أي بيانات من TradingView.")
        send("⚠️ تعذر جلب البيانات من TradingView في الوقت الحالي.")
        return

    # التصفية بحسب القاموس المعتمد
    filtered_df = df[df["ticker"].isin(crypto_dict.keys())]

    # في حال لم تتطابق أي عملة من القاموس مع الفلتر الحالي، أظهر أسرع 10 عملات حركة من نتائج السوق مباشرة
    if filtered_df.empty:
        filtered_df = df.head(MAX_SHOWN)

    header = f"🚨 <b>تحديث سوق الكريبتو</b>\nℹ️ <i>{condition_info}</i>"
    blocks = []

    for idx, (_, row) in enumerate(filtered_df.head(MAX_SHOWN).iterrows(), 1):
        ticker = row["ticker"]
        arabic_name = escape_html(crypto_dict.get(ticker, ticker))
        tv_url = f"https://www.tradingview.com/chart/?symbol={EXCHANGE_NAME}:{ticker}"

        price = float(row.get("close", 0.0))
        change = float(row.get("change", 0.0))
        volume = float(row.get("volume", 0.0))

        curr_count = counts.get(ticker, 0) + 1
        counts[ticker] = curr_count

        lvl = calculate_levels(price)

        lines = [
            f"🔥 <b>#{idx} {arabic_name} ({ticker})</b>",
            f"🚨 🛑 <b>[تنبيه رقم {curr_count}]</b>",
            f"💵 <b>السعر:</b> ${price:.4f} | <b>التغير:</b> {change:+.2f}%",
            f"📊 <b>حجم التداول (Vol):</b> {int(volume):,}",
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
