import os
import json
import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# ================================
# إعدادات التلغرام والبيئة
# ================================
TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

RIYADH = ZoneInfo("Asia/Riyadh")
SEEN_FILE = "seen_stocks.json"
MAX_SHOWN = 10
CHECK_INTERVAL_SECONDS = 120  # التكرار كل دقيقتين

# ================================
# إدارة ملف التكرارات والتحقق اليومي
# ================================
def load_seen():
    """تحميل سجل التنبيهات لليوم الحالي"""
    today = datetime.now(RIYADH).strftime("%Y-%m-%d")
    try:
        if os.path.exists(SEEN_FILE):
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") == today:
                return today, data.get("counts", {})
    except Exception as e:
        print(f"⚠️ خطأ في قراءة ملف السجل: {e}")
    return today, {}

def save_seen(today, counts):
    """حفظ سجل التنبيهات مع التوقيت"""
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "date": today,
                "counts": counts,
                "last_update": datetime.now(RIYADH).strftime("%H:%M:%S")
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ خطأ في حفظ ملف السجل: {e}")

# ================================
# تحديد نوع الجلسة بناءً على توقيت السعودية (صيفي UTC+3)
# ================================
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
        return "closed", "⏸️ المغلق (خارج أوقات التداول)"

# ================================
# جلب بيانات الأسهم وبناء الفلاتر (TradingView API)
# ================================
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
            "name",                             # رمز السهم
            "description",                      # اسم الشركة
            "close",                            # السعر الحالي
            change_field,                        # التغير % الخاص بالجلسة
            volume_field,                        # حجم تداول الجلسة
            "sector",                           # القطاع
            "industry",                         # الصناعة
            "country",                          # الدولة
            "exchange"                          # البورصة
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

# ================================
# أدوات المساعدة
# ================================
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
        print("⚠️ BOT_TOKEN أو CHAT_ID غير محدد.")
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
    except Exception as e:
        print(f"❌ خطأ في إرسال التليجرام: {e}")

# ================================
# التشغيل الرئيسي
# ================================
def main():
    print("🚀 تم تشغيل ماسح الأسهم (مع عداد التكرارات)...")

    while True:
        try:
            today, counts = load_seen()
            now_str = datetime.now(RIYADH).strftime("%H:%M:%S")
            session_key, session_name = get_current_session()

            if session_key == "closed":
                print(f"⏸️ [{now_str}] السوق مغلق حالياً. ينتظر 5 دقائق...")
                time.sleep(300)
                continue

            print(f"⏰ [{now_str}] جاري الفحص | الجلسة: {session_name}")
            stocks = fetch_filtered_stocks(session_key)

            if stocks:
                header = (
                    f"🇺🇸 <b>رادار الأسهم الأمريكية</b>\n"
                    f"⏱️ <b>الجلسة:</b> {session_name}\n"
                    f"📅 <b>الوقت:</b> <code>{now_str} KSA</code>\n"
                    f"-----------------------------------"
                )
                
                blocks = []
                for item in stocks:
                    d = item.get("d", [])
                    if len(d) < 9:
                        continue

                    symbol = escape_html(d[0])
                    price = float(d[2] or 0)
                    change_pct = float(d[3] or 0)
                    volume = float(d[4] or 0)
                    sector = escape_html(d[5])
                    industry = escape_html(d[6])
                    country = escape_html(d[7])
                    exchange = escape_html(d[8])

                    # زياوة عداد التكرار للسهم
                    curr_count = counts.get(symbol, 0) + 1
                    counts[symbol] = curr_count

                    # صياغة عنوان التنبيه (Alert أو Alert 2 أو Alert 3 ...)
                    alert_title = "🚨 Alert" if curr_count == 1 else f"🚨 Alert {curr_count}"

                    tv_url = f"https://www.tradingview.com/chart/?symbol={exchange}:{symbol}"

                    # المخرجات بالشكل والمراحل المطلوبة تماماً
                    lines = [
                        f"{alert_title}",
                        f"<b>رمز السهم:</b> {symbol}",
                        f"<b>القطاع:</b> {sector}",
                        f"<b>الصناعة:</b> {industry}",
                        f"<b>الدوله:</b> {country}",
                        f"<b>السعر الحالي:</b> ${price:.2f}",
                        f"<b>التغير للجلسة الحالية +-٪:</b> {change_pct:+.2f}%",
                        f"<b>Vol:</b> {format_number(volume)}",
                        f"<b>الشارت TradingView:</b> <a href='{tv_url}'>فتح الشارت</a>",
                        "-----------------------------------"
                    ]
                    blocks.append("\n".join(lines))

                # حفظ حالة التكرارات
                save_seen(today, counts)

                # إرسال الرسالة
                full_message = header + "\n\n" + "\n\n".join(blocks)
                send_telegram(full_message)
                print(f"✅ تم إرسال التقرير ({len(blocks)} سهم) وتحديث السجل.")
            else:
                print(f"ℹ️ [{now_str}] لا توجد أسهم تطابق الشروط حالياً.")

        except Exception as e:
            print(f"❌ حدث خطأ أثناء التشغيل: {e}")

        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
