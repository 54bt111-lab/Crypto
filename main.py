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


def fetch_crypto_from_binance_us():
    """المحاولة الأولى: جلب البيانات عبر Binance.us لتفادي الحظر الأمريكي على GitHub Actions"""
    url = "https://api.binance.us/api/v3/ticker/24hr"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        df = pd.DataFrame(data)
        df["price"] = df["lastPrice"].astype(float)
        df["change"] = df["priceChangePercent"].astype(float)
        df["quoteVolume"] = df["quoteVolume"].astype(float)
        df["ticker"] = df["symbol"]

        df_usdt = df[df["ticker"].str.endswith("USDT")].copy()
        df_sorted = df_usdt.sort_values(by="change", ascending=False)
        return df_sorted, "Binance US API"
    except Exception as e:
        print(f"⚠️ فشل Binance US API: {e}")

    # المحاولة الثانية (الاحتياطية): جلب البيانات عبر CoinGecko API المفتوح عالمياً
    try:
        cg_url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "price_change_percentage_24h_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": "false"
        }
        resp = requests.get(cg_url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        cg_data = resp.json()

        records = []
        for coin in cg_data:
            records.append({
                "ticker": f"{coin['symbol'].upper()}USDT",
                "price": float(coin.get("current_price", 0.0)),
                "change": float(coin.get("price_change_percentage_24h", 0.0)),
                "quoteVolume": float(coin.get("total_volume", 0.0))
            })

        df_cg = pd.DataFrame(records)
        return df_cg, "CoinGecko API (Global)"
    except Exception as e:
        print(f"⚠️ فشل CoinGecko API: {e}")

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

    print(f"⏰ [{now_time}] جاري إجراء الفحص عبر الواجهة المفتوحة...")

    df, source_name = fetch_crypto_from_binance_us()
    crypto_dict = get_crypto_dict()

    if df.empty:
        print("❌ تعذر جلب البيانات من المصادر.")
        send("⚠️ تعذر جلب البيانات من المصادر المتاحة حالياً.")
        return

    # التصفية بحسب القاموس
    filtered_df = df[df["ticker"].isin(crypto_dict.keys())]

    if filtered_df.empty or len(filtered_df) < 3:
        filtered_df = df.head(MAX_SHOWN)

    header = f"🚨 <b>تحديث سوق الكريبتو (أعلى العملات زخماً)</b>\nℹ️ <i>المصدر: {source_name}</i>"
    blocks = []

    for idx, (_, row) in enumerate(filtered_df.head(MAX_SHOWN).iterrows(), 1):
        ticker = str(row["ticker"])
        arabic_name = escape_html(crypto_dict.get(ticker, ticker.replace("USDT", "")))
        tv_url = f"https://www.tradingview.com/chart/?symbol={EXCHANGE_NAME}:{ticker}"

        price = float(row["price"])
        change = float(row["change"])
        usdt_volume = float(row["quoteVolume"]) / 1_000_000

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
