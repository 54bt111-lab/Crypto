import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# ================================
# إعدادات التلغرام والبيئة
# ================================
TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

RIYADH = ZoneInfo("Asia/Riyadh")
MAX_SHOWN = 10

def get_current_session():
    now = datetime.now(RIYADH)
    time_num = now.hour * 100 + now.minute

    if 1100 <= time_num < 1630:
        return "premarket", "🌅 Pre-Market (ما قبل الافتتاح)"
    elif 1630 <= time_num < 2300:
        return "market", "🔔 Main Session (السوق الرئيسي)"
    elif time_num >= 2300 or time_num < 300:
        return "postmarket", "🌙 Post-Market (ما بعد الإغلاق)"
    else:
        # للاختبار خارج أوقات العمل، نفحص على بيانات السوق الرئيسي
        return "market", "🧪 وضع الاختبار التجريبي"

def fetch_filtered_stocks(session_type):
    url = "https://scanner.tradingview.com/america/scan"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json"
    }

    change_field = "change"
    volume_field = "volume"
    
    if session_type == "premarket":
        change_field = "premarket_change"
        volume_field = "premarket_volume"
    elif session_type == "postmarket":
        change_field = "postmarket_change"
        volume_field = "postmarket_volume"

    payload = {
        "filter": [
            {"left": "float_shares_outstanding_current", "operation": "less", "right": 50_000_000},
            {"left": volume_field, "operation": "greater", "right": 30_000},
            {"left": change_field, "operation": "greater", "right": 2.0},
            {"left": "Change.5m", "operation": "greater", "right": 0.0},
            {"left": "average_volume_10d_calc", "operation": "greater", "right": 100_000},
            {"left": "relative_volume_10d_calc", "operation": "greater", "right": 1.5},
            {"left": "close", "operation": "less", "right": 50.0},
            {"left": "exchange", "operation": "in_range", "right": ["NYSE", "NASDAQ", "AMEX"]}
        ],
        "options": {"lang": "en"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": [
            "name",
            "description",
            "close",
            change_field,
            volume_field,
            "sector",
            "industry",
            "country",
            "float_shares_outstanding_current",
            "average_volume_10d_calc",
            "relative_volume_10d_calc",
            "Change.5m",
            "exchange"
        ],
        "sort": {"sortBy": change_field, "sortOrder": "desc"},
        "range": [0, MAX_SHOWN]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=12)
        response.raise_for_status()
        return response.json().get("data", [])
    except Exception as e:
        print(f"❌ خطأ أثناء جلب البيانات: {e}")
        return []

def escape_html(text):
    if not text:
        return "غير محدد"
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def format_number(num):
    if not num:
        return "0"
    if num >= 1_000_000:
        return f"{num / 1_000_000:.2f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return f"{num:.2f}"

def send_telegram(text):
    if not TOKEN or not CHAT_ID:
        print("⚠️ BOT_TOKEN أو CHAT_ID غير محدد في متغيرات البيئة.")
        return
    try:
        res = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        res.raise_for_status()
        print("✅ تم إرسال رسالة الاختبار بنجاح إلى التليجرام!")
    except Exception as e:
        print(f"❌ خطأ في الإرسال: {e}")

def test_run():
    now_str = datetime.now(RIYADH).strftime("%H:%M:%S")
    session_key, session_name = get_current_session()

    print(f"🧪 [اختبار فوري] جاري جلب الأسهم... ({now_str} KSA)")
    stocks = fetch_filtered_stocks(session_key)

    if not stocks:
        print("ℹ️ لم يتم العثور على أسهم تطابق الشروط حالياً، جاري إرسال رسالة تجريبية...")
        send_telegram(f"🧪 <b>تأكيد اتصال البوت</b>\n📅 الوقت: <code>{now_str} KSA</code>\nℹ️ لا توجد أسهم تطابق كافة الشروط حالياً.")
        return

    header = (
        f"🧪 <b>تنسيق تقرير الاختبار الفوري</b>\n"
        f"⏱️ <b>الجلسة:</b> {session_name}\n"
        f"📅 <b>الوقت:</b> <code>{now_str} KSA</code>\n"
        f"-----------------------------------"
    )
    
    blocks = []
    for idx, item in enumerate(stocks, 1):
        d = item.get("d", [])
        if len(d) < 13:
            continue

        symbol = escape_html(d[0])
        company_name = escape_html(d[1])
        price = float(d[2] or 0)
        change_pct = float(d[3] or 0)
        volume = float(d[4] or 0)
        sector = escape_html(d[5])
        industry = escape_html(d[6])
        country = escape_html(d[7])
        float_shares = float(d[8] or 0)
        avg_vol = float(d[9] or 0)
        rvol = float(d[10] or 0)
        change_5m = float(d[11] or 0)
        exchange = escape_html(d[12])

        tv_url = f"https://www.tradingview.com/chart/?symbol={exchange}:{symbol}"

        lines = [
            f"🔥 <b>#{idx} {symbol}</b> - {company_name}",
            f"🏛️ <b>البورصة:</b> {exchange} | 🌐 <b>الدولة:</b> {country}",
            f"🏢 <b>القطاع:</b> {sector}",
            f"🏭 <b>الصناعة:</b> {industry}",
            f"💵 <b>السعر:</b> ${price:.2f} | <b>التغير:</b> +{change_pct:.2f}%",
            f"⚡ <b>أداء 5 دقائق:</b> +{change_5m:.2f}%",
            f"📊 <b>الحجم:</b> {format_number(volume)}",
            f"📈 <b>RVOL:</b> {rvol:.2f}x | <b>المتوسط:</b> {format_number(avg_vol)}",
            f"🏊 <b>Float:</b> {format_number(float_shares)}",
            f"🔗 <b>الشارت:</b> <a href='{tv_url}'>TradingView</a>",
            "-----------------------------------"
        ]
        blocks.append("\n".join(lines))

    full_message = header + "\n\n" + "\n\n".join(blocks)
    send_telegram(full_message)

if __name__ == "__main__":
    test_run()
