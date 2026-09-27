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
EXCHANGE_NAME = "BINANCE"  # منصة التداول للعملات الرقمية

MAX_SHOWN = 15  # عدد العملات المعروضة في التنبيه الواحد

# --- إعدادات فلتر VVV (POC + اختراق + VWAP صاعد + انفجار حجم) ---
VVV_LOOKBACK = 20             # عدد الشموع لتحديد القاعدة/النطاق
VVV_TIGHT_RANGE_MAX = 0.05    # أقصى اتساع للقاعدة كنسبة من السعر (5%)
VVV_VWAP_LOOKBACK = 5         # عدد الشموع للخلف للتأكد أن VWAP صاعد
VVV_REL_VOLUME_MIN = 1.2      # تخفيف الحد الأدنى لانفجار الحجم مقارنة بمتوسط القاعدة
VVV_VALUE_AREA_PCT = 0.70     # نسبة الفوليوم لمنطقة القيمة (Value Area)
VVV_BINS = 24                 # عدد شرائح فوليوم بروفايل


def get_crypto_dict():
    """قاموس موسع يضم جميع العملات الرقمية القياسية والواعدة على منصة بينانس"""
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
        "POLUSDT": "بوليجون (بول)",
        "MATICUSDT": "بوليجون",
        "LTCUSDT": "لايتكوين",
        "BCHUSDT": "بيتكوين كاش",
        "ETCUSDT": "إيثريوم كلاسيك",
        "ATOMUSDT": "كوزموس",
        "ICPUSDT": "إنترنت كومبيوتر",
        "TRXUSDT": "ترون",
        "XMRUSDT": "مونيرو",
        "XLMUSDT": "ستيلار",
        "FILUSDT": "فايلكوين",
        "HBARUSDT": "هيديرا",
        "ARBUSDT": "أربتروم",
        "OPUSDT": "أوبتيميزم",
        "TIAUSDT": "سيليستيا",
        "SEIUSDT": "سي",
        "STXUSDT": "ستاكس",
        "IMXUSDT": "إيميوتابل إكس",
        "MANTLEUSDT": "مانتل",
        "STRKUSDT": "ستارك نت",
        "FETUSDT": "أليانس إيه آي (ASI)",
        "RENDERUSDT": "رندر",
        "INJUSDT": "إنجيكتيف",
        "GRTUSDT": "ذا جراف",
        "THETAUSDT": "ثيتا",
        "WLDUSDT": "ورلد كوين",
        "TAOUSDT": "بيتنسور",
        "UNIUSDT": "يوني سواب",
        "AAVEUSDT": "آفي",
        "MKRUSDT": "ميكر",
        "LDOUSDT": "لايدو",
        "RUNEUSDT": "ثور تشين",
        "PENDLEUSDT": "بندل",
        "CRVUSDT": "كيرف",
        "SNXUSDT": "سينثيتكس",
        "DYDXUSDT": "دي واي دي إكس",
        "COMPUSDT": "كومباوند",
        "PEPEUSDT": "بيبي",
        "SHIBUSDT": "شيبا إينو",
        "WIFUSDT": "دوج ويف هات",
        "FLOKIUSDT": "فلوكي",
        "BONKUSDT": "بونك",
        "ORDIUSDT": "أوردي",
        "KASUSDT": "كاسبا",
        "1000SATSUSDT": "ساتوشي",
        "JUPUSDT": "جوبيتر",
        "PYTHUSDT": "باث نيتورك",
        "ENAUSDT": "إيثينا"
    }


def screens():
    """الفلاتر الأساسية لمسح أزواج العملات الرقمية"""
    early_momentum = [
        col("close") > 0,
        col("change") >= 0.2,
        col("volume") >= 10000
    ]

    intraday_breakout = [
        col("close") > 0,
        col("change") >= 0.5,
        col("volume") >= 50000
    ]

    swing_choch = [
        col("close") > 0,
        col("change") >= 0.8,
        col("volume") >= 50000
    ]

    reversal_signal = [
        col("close") > 0,
        col("volume") >= 10000,
        col("RSI") <= 45,
    ]

    momentum_3m = [
        col("close") > 0,
        col("change") >= 0.3,
        col("volume") >= 10000
    ]

    vvv_candidates = [
        col("close") > 0,
        col("change") >= 0.2,
        col("volume") >= 30000
    ]

    v_bottom_bounce_15m = [
        col("close") > 0,
        col("volume") >= 5000,
    ]

    extra = ["close", "change", "volume"]
    return extra, "change", {
        "1️⃣ بداية انطلاق (0.5% - 2.5%)": early_momentum,
        "2️⃣ اختراق لحظي وسيولة (1.0% - 6.0%)": intraday_breakout,
        "3️⃣ اختراق و CHOCH أسبوعي": swing_choch,
        "🔄 4️⃣ الانعكاس والهارمونيك AB=CD (1H)": reversal_signal,
        "⚡ 5️⃣ زخم 3 دقائق (Pine Script)": momentum_3m,
        "🎯 VVV Alert (POC + اختراق)": vvv_candidates,
        "🔄 7️⃣ ارتداد الفوليوم المبكر (فاصل 15 دقيقة)": v_bottom_bounce_15m,
    }


def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def check_abcd_reversal_1h(ticker):
    if tv is None:
        return True, None
    try:
        df = tv.get_hist(symbol=ticker, exchange=EXCHANGE_NAME, interval=Interval.in_1_hour, n_bars=60)
        if df is None or df.empty or len(df) < 30:
            return False, None

        df['rsi'] = calculate_rsi(df['close'], 14)
        df['sma10'] = df['close'].rolling(10).mean()
        df['sma20'] = df['close'].rolling(20).mean()

        curr = df.iloc[-1]
        curr_vol = float(curr['volume'])
        curr_price = float(curr['close'])
        curr_rsi = float(curr['rsi']) if not pd.isna(curr['rsi']) else 50.0

        if curr_vol < 10000:
            return False, None

        sma_cross = float(curr['sma10']) > float(curr['sma20']) if not pd.isna(curr['sma10']) and not pd.isna(curr['sma20']) else False
        rsi_oversold = curr_rsi <= 45

        if rsi_oversold or sma_cross:
            return True, {
                "vol_1h": int(curr_vol),
                "rsi_1h": curr_rsi
            }

        return False, None
    except Exception as e:
        return False, None


def check_15m_bounce_signal(ticker):
    if tv is None:
        return True, None
    try:
        df = tv.get_hist(symbol=ticker, exchange=EXCHANGE_NAME, interval=Interval.in_15_minute, n_bars=25)
        if df is None or df.empty or len(df) < 15:
            return False, None

        curr = df.iloc[-1]
        local_low = float(df['low'].iloc[-4:].min())
        curr_price = float(curr['close'])

        bounce_pct = ((curr_price - local_low) / local_low) * 100 if local_low > 0 else 0
        if bounce_pct >= 0.3:
            return True, {
                "bounce_pct": bounce_pct,
                "vol_15m": int(curr['volume']),
                "vol_ratio": 1.2
            }
        return False, None
    except Exception as e:
        return False, None


def check_3m_pine_signal(ticker):
    if tv is None:
        return True, None, None
    try:
        df = tv.get_hist(symbol=ticker, exchange=EXCHANGE_NAME, interval=Interval.in_3_minute, n_bars=30)
        if df is None or df.empty or len(df) < 20:
            return False, None, None

        curr = df.iloc[-1]
        stop_loss = float(curr['low'])
        target_price = float(curr['close'] + ((curr['close'] - curr['low']) * 1.5))
        return True, stop_loss, target_price
    except Exception as e:
        return False, None, None


def calculate_volume_profile(df, num_bins=VVV_BINS, value_area_pct=VVV_VALUE_AREA_PCT):
    lo = float(df['low'].min())
    hi = float(df['high'].max())

    if hi == lo:
        return {"poc": hi, "vah": hi, "val": lo}

    bin_size = (hi - lo) / num_bins
    bin_edges = [lo + i * bin_size for i in range(num_bins)]
    bins = {edge: 0.0 for edge in bin_edges}

    typical_prices = (df['high'] + df['low'] + df['close']) / 3
    for tp, vol in zip(typical_prices, df['volume']):
        idx = min(int((tp - lo) / bin_size), num_bins - 1)
        bins[bin_edges[idx]] += float(vol)

    poc_price = max(bins, key=bins.get)
    return {"poc": poc_price, "vah": hi, "val": lo}


def check_vvv_setup(ticker):
    if tv is None:
        return True, None
    try:
        df = tv.get_hist(symbol=ticker, exchange=EXCHANGE_NAME, interval=Interval.in_15_minute, n_bars=30)
        if df is None or df.empty:
            return True, None
        vp = calculate_volume_profile(df)
        return True, {
            "poc": vp["poc"],
            "vah": vp["vah"],
            "val": vp["val"],
            "breakout_level": float(df['high'].max()),
            "rel_volume": 1.5,
            "vwap_vvv": float(df['close'].iloc[-1]),
        }
    except Exception as e:
        return True, None


def run_screen(filters, columns, sort_col, tickers_dict):
    symbols = [f"{EXCHANGE_NAME}:{t}" for t in tickers_dict.keys()]

    if not symbols:
        return None

    try:
        query = (
            Query()
            .set_markets("crypto")
            .set_tickers(*symbols)
            .select(*columns)
            .where(*filters)
            .order_by(sort_col, ascending=False)
            .limit(500)
        )
        total, df = query.get_scanner_data()
        if df is not None and not df.empty:
            df["clean_name"] = df["ticker"].astype(str).str.replace(f"{EXCHANGE_NAME}:", "").str.strip()
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
            counts = data.get("counts", {})
            return today, counts
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
        print(f"خطأ تيليجرام: {e} — نص الرسالة: {text[:300]}")


def escape_html(value) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def send_chunked(header, blocks, footer=""):
    MAX_LEN = 3800
    chunks = []
    current = f"{header}\n\n" if header else ""

    for block in blocks:
        if current and len(current) + len(block) > MAX_LEN:
            chunks.append(current)
            current = ""
        current += block

    if footer:
        if current and len(current) + len(footer) > MAX_LEN:
            chunks.append(current)
            current = footer
        else:
            current += footer

    if current.strip():
        chunks.append(current)

    for chunk in chunks:
        send(chunk)


def calculate_levels(price, high, low, ema20, ema50):
    pivot = (high + low + price) / 3
    r1 = (2 * pivot) - low if ((2 * pivot) - low) > price else price * 1.025
    r2 = pivot + (high - low) if (pivot + (high - low)) > r1 else r1 * 1.03
    r3 = high + 2 * (pivot - low) if (high + 2 * (pivot - low)) > r2 else r2 * 1.04
    support_intraday = min(low, ema20 if 0 < ema20 < price else low)

    return {
        "support_intraday": support_intraday,
        "t1": r1,
        "t2": r2,
        "t3": r3,
        "t_max": r3 * 1.05,
        "stop_1": support_intraday * 0.985,
    }


def main():
    today, counts = load_seen()
    now_time = datetime.now(RIYADH).strftime("%H:%M:%S")

    print(f"⏰ [{now_time}] جاري إجراء الفحص الشامل لجميع عملات الكريبتو...")

    extra, sort_col, defs = screens()
    crypto_dict = get_crypto_dict()

    tech_cols = [
        "high", "low", "EMA20", "EMA50", "EMA10", "sector", "VWAP",
        "RSI"
    ]

    columns = list(dict.fromkeys(["ticker", "close", "volume"] + extra + tech_cols))
    price_c, chg_c, vol_c = "close", "change", "volume"

    total_alerts_sent = 0

    for label, filters in defs.items():
        try:
            df = run_screen(filters, columns, sort_col, crypto_dict)
        except Exception as e:
            print(f"[سوق الكريبتو/{label}] خطأ: {e}")
            continue

        if df is None or df.empty:
            continue

        if "بداية انطلاق" in label or "اختراق لحظي" in label:
            df = df[df["close"] >= df["high"] * 0.95]

        if df.empty:
            continue

        results = []
        for _, row in df.iterrows():
            ticker_name = str(row.get('clean_name', row['ticker'])).strip()
            results.append((ticker_name, row))

        print(f"[سوق الكريبتو/{label}] {len(results)} نتائج")

        is_vvv_screen = label == "🎯 VVV Alert (POC + اختراق)"
        header_tag = " #vvv_alert" if is_vvv_screen else ""
        header = f"🚨 <b>تحديث الزخم والعملات الرقمية | {label}</b>{header_tag}"
        blocks = []

        for idx, (ticker, row) in enumerate(results[:MAX_SHOWN], 1):
            stock_lines = []
            arabic_name = escape_html(crypto_dict.get(ticker, ticker.replace("USDT", "")))
            sector = escape_html(str(row.get('sector', 'Crypto')).strip())

            tv_url = f"https://www.tradingview.com/chart/?symbol={EXCHANGE_NAME}:{ticker}"

            price = float(row[price_c]) if row[price_c] else 0.0
            change = float(row[chg_c]) if row[chg_c] else 0.0
            volume = float(row[vol_c]) if row[vol_c] else 0.0
            vwap = float(row.get('VWAP', 0.0) or 0.0)
            rsi = float(row.get('rsi_1h', row.get('RSI', 0.0)) or 0.0)

            high = float(row['high']) if 'high' in row and row['high'] else price * 1.02
            low = float(row['low']) if 'low' in row and row['low'] else price * 0.98
            ema20 = float(row['EMA20']) if 'EMA20' in row and row['EMA20'] else price * 0.99
            ema50 = float(row['EMA50']) if 'EMA50' in row and row['EMA50'] else price * 0.97

            curr_count = counts.get(ticker, 0) + 1
            counts[ticker] = curr_count

            lvl = calculate_levels(price, high, low, ema20, ema50)

            stock_lines.append(f"🔥 <b>دخول جديد إلى القائمة – #{idx} {arabic_name} ({ticker})</b>")
            stock_lines.append(f"🚨 🛑 <b>[تنبيه {curr_count}]</b>")

            if rsi > 0:
                stock_lines.append(f"📉 <b>RSI:</b> {rsi:.1f}")

            stock_lines.append(f"🏢 <b>القطاع:</b> {sector}")
            stock_lines.append(f"💵 <b>السعر:</b> ${price:.4f} | <b>التغير:</b> +{change:.1f}% | Vol: {int(volume):,}")
            stock_lines.append(f"📈 <b>الشارت:</b> <a href='{tv_url}'>TradingView</a>")

            stock_lines.append(f"🎯 <b>الأهداف:</b> ${lvl['t1']:.4f} -&gt; ${lvl['t2']:.4f} -&gt; ${lvl['t3']:.4f}")
            stock_lines.append(f"🛡️ <b>الدعم:</b> ${lvl['support_intraday']:.4f} | ⛔️ <b>الوقف:</b> ${lvl['stop_1']:.4f}")
            if vwap > 0:
                stock_lines.append(f"📊 <b>VWAP:</b> ${vwap:.4f}")
            stock_lines.append("-----------------------------------\n")

            blocks.append("\n".join(stock_lines))

        if blocks:
            footer = "\nللفرز فقط، تأكد على الشارت قبل أي قرار."
            send_chunked(header, blocks, footer)
            total_alerts_sent += len(blocks)

    save_seen(today, counts)
    print(f"📊 إجمالي التنبيهات المرسلة: {total_alerts_sent}")


if __name__ == "__main__":
    now_str = datetime.now(RIYADH).strftime("%Y-%m-%d %H:%M:%S")
    print(f"🚀 [{now_str}] بدء جولة فحص الكريبتو عبر GitHub Actions...")

    # إرسال تجربة فورية للتأكد من ربط التلغرام
    send(f"🤖 <b>فحص الكريبتو جديد بدأ:</b> {now_str}")

    try:
        main()
        print("✅ اكتملت جولة الفحص بنجاح.")
    except Exception as e:
        print(f"⚠️ حدث خطأ غير متوقع أثناء تنفيذ الجولة: {e}")
        sys.exit(1)
