import json
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from tradingview_screener import Query, col

# استيراد TvDatafeed لحساب البيانات التاريخية والنماذج
try:
    from tvdatafeed import TvDatafeed, Interval
    tv = TvDatafeed()
except Exception as e:
    print(f"⚠️ تحذير: لم يتم الاتصال بـ TvDatafeed: {e}")
    tv = None

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
VVV_REL_VOLUME_MIN = 1.5      # الحد الأدنى لانفجار الحجم مقارنة بمتوسط القاعدة
VVV_VALUE_AREA_PCT = 0.70     # نسبة الفوليوم لمنطقة القيمة (Value Area)
VVV_BINS = 24                 # عدد شرائح فوليوم بروفايل


def get_crypto_dict():
    """قاموس موسع يضم جميع العملات الرقمية القياسية والواعدة على منصة بينانس"""
    return {
        # العملات الكبرى القياسية (Top Tier)
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
        
        # شبكات الطبقة الثانية والحلول (Layer 2 / Scaling)
        "ARBUSDT": "أربتروم",
        "OPUSDT": "أوبتيميزم",
        "TIAUSDT": "سيليستيا",
        "SEIUSDT": "سي",
        "STXUSDT": "ستاكس",
        "IMXUSDT": "إيميوتابل إكس",
        "MANTLEUSDT": "مانتل",
        "STRKUSDT": "ستارك نت",

        # الذكاء الاصطناعي والبيانات (AI & Data)
        "FETUSDT": "أليانس إيه آي (ASI)",
        "RENDERUSDT": "رندر",
        "INJUSDT": "إنجيكتيف",
        "GRTUSDT": "ذا جراف",
        "THETAUSDT": "ثيتا",
        "WLDUSDT": "ورلد كوين",
        "TAOUSDT": "بيتنسور",

        # التمويل اللامركزي (DeFi & Infrastructure)
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

        # عملات الميم والعملات الشائعة (Memes & Trending)
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
    
    # 1. بداية انطلاق (0.5% - 2.5%) - فوليوم 100k
    early_momentum = [
        col("close") > 0,
        col("change") >= 0.5,
        col("change") <= 2.5,
        col("volume") >= 100000,
        col("close") > col("VWAP")
    ]

    # 2. اختراق لحظي وسيولة (1.0% - 6.0%) - فوليوم 100k
    intraday_breakout = [
        col("close") > 0,
        col("change") >= 1.0,
        col("change") <= 6.0,
        col("volume") >= 100000,
        col("close") > col("VWAP"),
        col("close") > col("EMA20")
    ]

    # 3. اختراق أسبوعي - فوليوم 100k
    swing_choch = [
        col("close") > 0,
        col("change") >= 1.0,
        col("volume") >= 100000,
        col("close") > col("EMA20"),
        col("close") > col("high|1W")
    ]

    # 4. فلتر الانعكاس الهارمونيك المطور
    reversal_signal = [
        col("close") > 0,
        col("volume") >= 20000,
        col("RSI") <= 40,
    ]

    # 5. زخم 3 دقائق (Pine Script)
    momentum_3m = [
        col("close") > 0,
        col("change") >= 0.5,
        col("volume") >= 10000,
        col("close") > col("VWAP"),
        col("close") > col("EMA10")
    ]

    # 6. فلتر VVV
    vvv_candidates = [
        col("close") > 0,
        col("change") >= 0.3,
        col("volume") >= 80000,
        col("close") > col("VWAP"),
    ]

    # 7. فلتر الارتداد المبكر (15 دقيقة)
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
    """حساب مؤشر RSI14"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def check_abcd_reversal_1h(ticker):
    """فحص نموذج الهارمونيك AB=CD وانعكاس الزخم على فاصل 1H"""
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

        if curr_vol < 20000:
            return False, None

        highs = df['high'].values
        lows = df['low'].values

        pivot_highs = []
        pivot_lows = []

        for i in range(2, len(df) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                pivot_highs.append((i, highs[i]))
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                pivot_lows.append((i, lows[i]))

        has_abcd = False
        prz_d = 0.0
        bc_ratio = 0.0

        if len(pivot_highs) >= 2 and len(pivot_lows) >= 1:
            for ph1 in reversed(pivot_highs[-4:]):
                a_idx, a_price = ph1
                b_candidates = [pl for pl in pivot_lows if pl[0] > a_idx]
                if not b_candidates:
                    continue
                b_idx, b_price = b_candidates[0]

                c_candidates = [ph for ph in pivot_highs if ph[0] > b_idx and ph[1] < a_price]
                if not c_candidates:
                    continue
                c_idx, c_price = c_candidates[0]

                if len(df) - 1 <= c_idx:
                    continue

                ab_len = a_price - b_price
                bc_len = c_price - b_price

                if ab_len <= 0 or bc_len <= 0:
                    continue

                ratio = bc_len / ab_len

                if 0.50 <= ratio <= 0.886:
                    target_d = c_price - ab_len
                    price_diff_pct = abs(curr_price - target_d) / target_d * 100

                    if price_diff_pct <= 2.5:
                        has_abcd = True
                        prz_d = target_d
                        bc_ratio = ratio * 100
                        break

        sma_cross = float(curr['sma10']) > float(curr['sma20']) if not pd.isna(curr['sma10']) and not pd.isna(curr['sma20']) else False
        rsi_oversold = curr_rsi <= 38
        is_green_candle = curr_price > float(curr['open'])

        if has_abcd and (rsi_oversold or sma_cross or is_green_candle):
            return True, {
                "vol_1h": int(curr_vol),
                "rsi_1h": curr_rsi,
                "has_abcd": True,
                "prz_d": prz_d,
                "bc_ratio": bc_ratio
            }
        elif not has_abcd and rsi_oversold and sma_cross:
            return True, {
                "vol_1h": int(curr_vol),
                "rsi_1h": curr_rsi,
                "has_abcd": False
            }

        return False, None
    except Exception as e:
        print(f"خطأ في فحص نموذج AB=CD للعملة {ticker}: {e}")
        return False, None


def check_15m_bounce_signal(ticker):
    """فحص الارتداد المبكر وتصاعد الفوليوم على فاصل 15 دقيقة"""
    if tv is None:
        return True, None

    try:
        df = tv.get_hist(symbol=ticker, exchange=EXCHANGE_NAME, interval=Interval.in_15_minute, n_bars=25)
        if df is None or df.empty or len(df) < 15:
            return False, None

        df['vol_sma10'] = df['volume'].rolling(window=10).mean()

        curr = df.iloc[-1]
        prev1 = df.iloc[-2]
        prev2 = df.iloc[-3]

        local_low = float(df['low'].iloc[-4:].min())
        curr_price = float(curr['close'])

        bounce_pct = ((curr_price - local_low) / local_low) * 100
        has_bounce = bounce_pct >= 0.8

        curr_vol = float(curr['volume'])
        has_min_vol_15m = curr_vol >= 5000

        vol_sma = float(curr['vol_sma10']) if curr['vol_sma10'] else 1.0
        vol_spike = curr_vol >= (vol_sma * 1.25)
        vol_ascending = (curr_vol > float(prev1['volume'])) and (float(prev1['volume']) > float(prev2['volume']))

        is_green_candle = curr_price > float(curr['open']) or curr_price >= float(curr['high']) * 0.998

        if has_bounce and has_min_vol_15m and (vol_spike or vol_ascending) and is_green_candle:
            return True, {
                "bounce_pct": bounce_pct,
                "vol_15m": int(curr_vol),
                "vol_ratio": curr_vol / vol_sma if vol_sma else 1.0
            }

        return False, None
    except Exception as e:
        print(f"خطأ في فحص ارتداد 15 دقيقة للعملة {ticker}: {e}")
        return False, None


def check_3m_pine_signal(ticker):
    """فحص شروط زخم 3 دقائق"""
    if tv is None:
        return True, None, None

    try:
        df = tv.get_hist(symbol=ticker, exchange=EXCHANGE_NAME, interval=Interval.in_3_minute, n_bars=30)
        if df is None or df.empty or len(df) < 20:
            return False, None, None

        df['ema10'] = df['close'].ewm(span=10, adjust=False).mean()
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['pv'] = df['typical_price'] * df['volume']
        df['vwap'] = df['pv'].cumsum() / df['volume'].cumsum()
        df['vol_sma20'] = df['volume'].rolling(window=20).mean()
        df['candle_change'] = ((df['close'] - df['open']) / df['open']) * 100

        curr = df.iloc[-1]
        prev1 = df.iloc[-2]
        prev2 = df.iloc[-3]

        curr_vol = float(curr['volume'])
        has_min_vol_3m = curr_vol >= 10000

        is_gain = curr['candle_change'] >= 0.8
        is_vol_acc = (curr_vol > prev1['volume']) and (prev1['volume'] > prev2['volume'])
        is_vol_spike = curr_vol > (curr['vol_sma20'] * 1.1)
        is_above_trend = (curr['close'] > curr['ema10']) or (curr['close'] > curr['vwap'])

        buy_signal = is_gain and is_vol_acc and is_vol_spike and is_above_trend and has_min_vol_3m

        if buy_signal:
            stop_loss = float(curr['low'])
            target_price = float(curr['close'] + ((curr['close'] - curr['low']) * 1.5))
            return True, stop_loss, target_price

        return False, None, None
    except Exception as e:
        print(f"خطأ في فحص فلتر 3 دقائق للعملة {ticker}: {e}")
        return False, None, None


def calculate_volume_profile(df, num_bins=VVV_BINS, value_area_pct=VVV_VALUE_AREA_PCT):
    """حساب POC و Value Area"""
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
    total_volume = sum(bins.values())
    target_volume = total_volume * value_area_pct
    sorted_prices = sorted(bins.keys())
    poc_idx = sorted_prices.index(poc_price)

    captured = bins[poc_price]
    lo_idx, hi_idx = poc_idx, poc_idx

    while captured < target_volume and (lo_idx > 0 or hi_idx < len(sorted_prices) - 1):
        vol_below = bins[sorted_prices[lo_idx - 1]] if lo_idx > 0 else -1
        vol_above = bins[sorted_prices[hi_idx + 1]] if hi_idx < len(sorted_prices) - 1 else -1

        if vol_above >= vol_below:
            hi_idx += 1
            captured += bins[sorted_prices[hi_idx]]
        else:
            lo_idx -= 1
            captured += bins[sorted_prices[lo_idx]]

    vah = sorted_prices[hi_idx] + bin_size
    val = sorted_prices[lo_idx]

    return {"poc": poc_price, "vah": vah, "val": val}


def check_vvv_setup(ticker):
    """فحص إعداد VVV"""
    if tv is None:
        return False, None

    try:
        n_bars = VVV_LOOKBACK + VVV_VWAP_LOOKBACK + 10
        df = tv.get_hist(symbol=ticker, exchange=EXCHANGE_NAME, interval=Interval.in_15_minute, n_bars=n_bars)
        if df is None or df.empty or len(df) < (VVV_LOOKBACK + VVV_VWAP_LOOKBACK + 1):
            return False, None

        base_df = df.iloc[-(VVV_LOOKBACK + 1):-1]
        current = df.iloc[-1]

        base_high = float(base_df['high'].max())
        base_low = float(base_df['low'].min())
        price = float(current['close'])

        range_pct = (base_high - base_low) / price if price else 1.0
        tight_base = range_pct <= VVV_TIGHT_RANGE_MAX
        breakout = price > base_high

        typical_price = (df['high'] + df['low'] + df['close']) / 3
        pv = typical_price * df['volume']
        vwap_series = pv.cumsum() / df['volume'].cumsum()
        vwap_now = float(vwap_series.iloc[-1])
        vwap_prior = float(vwap_series.iloc[-1 - VVV_VWAP_LOOKBACK])
        vwap_rising = vwap_now > vwap_prior
        price_above_vwap = price > vwap_now

        avg_volume = float(base_df['volume'].mean())
        rel_volume = float(current['volume']) / avg_volume if avg_volume else 0.0
        volume_spike = rel_volume >= VVV_REL_VOLUME_MIN

        is_setup = tight_base and breakout and vwap_rising and price_above_vwap and volume_spike
        if not is_setup:
            return False, None

        vp = calculate_volume_profile(df.iloc[-VVV_LOOKBACK:])

        return True, {
            "poc": vp["poc"],
            "vah": vp["vah"],
            "val": vp["val"],
            "breakout_level": base_high,
            "rel_volume": rel_volume,
            "vwap_vvv": vwap_now,
        }
    except Exception as e:
        print(f"خطأ في فحص إعداد VVV للعملة {ticker}: {e}")
        return False, None


def run_screen(filters, columns, sort_col, tickers_dict):
    symbols = [f"{EXCHANGE_NAME}:{t}" for t in tickers_dict.keys()]

    if not symbols:
        return None

    query = (
        Query()
        .set_tickers(*symbols)
        .select(*columns)
        .where(*filters)
        .order_by(sort_col, ascending=False)
        .limit(500)
    )

    try:
        _, df = query.get_scanner_data()
    except Exception as e:
        print(f"خطأ في الاستعلام من TradingView: {e}")
        df = None

    if df is not None and not df.empty:
        df["clean_name"] = df["name"].astype(str).str.replace(f"{EXCHANGE_NAME}:", "").str.strip()
        return df

    return df


def load_seen():
    """تحميل سجل التنبيهات مع تصفير السجل تلقائيًا عند بداية يوم جديد"""
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
    """حفظ سجل التنبيهات"""
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
    """تهريب رموز HTML لتيليجرام"""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def send_chunked(header, blocks, footer=""):
    """إرسال التنبيهات مقسمة لحزم آمنة تحت حد حروف تلغرام"""
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

    t1, t2, t3 = r1, r2, r3
    t_max = r3 * 1.05
    stop_1 = support_intraday * 0.985

    return {
        "support_intraday": support_intraday,
        "t1": t1,
        "t2": t2,
        "t3": t3,
        "t_max": t_max,
        "stop_1": stop_1,
    }


def main():
    today, counts = load_seen()
    now_time = datetime.now(RIYADH).strftime("%H:%M:%S")

    print(f"⏰ [{now_time}] جاري إجراء الفحص الشامل لجميع عملات الكريبتو...")

    extra, sort_col, defs = screens()
    crypto_dict = get_crypto_dict()

    tech_cols = [
        "high", "low", "EMA20", "EMA50", "EMA10", "sector", "VWAP",
        "price_52_week_high", "price_52_week_low",
        "high|1W", "high|2W", "RSI", "SMA10", "SMA20", "SMA10|1", "SMA20|1"
    ]

    columns = list(dict.fromkeys(["name", "close", "volume"] + extra + tech_cols))
    price_c, chg_c, vol_c = "close", "change", "volume"

    for label, filters in defs.items():
        try:
            df = run_screen(filters, columns, sort_col, crypto_dict)
        except Exception as e:
            print(f"[سوق الكريبتو/{label}] خطأ: {e}")
            continue

        if df is None or df.empty:
            continue

        if "بداية انطلاق" in label:
            df = df[df["close"] >= df["high"] * 0.98]
        elif "اختراق لحظي" in label:
            df = df[df["close"] >= df["high"] * 0.98]
        elif "الانعكاس" in label:
            if tv is not None:
                valid_rows = []
                for _, row in df.iterrows():
                    ticker_name = str(row.get('clean_name', row['name'])).strip()
                    is_valid, abcd_info = check_abcd_reversal_1h(ticker_name)
                    if is_valid:
                        row_dict = row.to_dict()
                        if abcd_info:
                            row_dict.update(abcd_info)
                        valid_rows.append(row_dict)
                df = pd.DataFrame(valid_rows)
        elif "15 دقيقة" in label:
            if tv is not None:
                valid_rows = []
                for _, row in df.iterrows():
                    ticker_name = str(row.get('clean_name', row['name'])).strip()
                    is_valid, bounce_info = check_15m_bounce_signal(ticker_name)
                    if is_valid:
                        row_dict = row.to_dict()
                        row_dict.update(bounce_info)
                        valid_rows.append(row_dict)
                df = pd.DataFrame(valid_rows)
        elif label == "⚡ 5️⃣ زخم 3 دقائق (Pine Script)":
            if tv is not None:
                valid_rows = []
                for _, row in df.iterrows():
                    ticker_name = str(row.get('clean_name', row['name'])).strip()
                    is_valid, sl_3m, tp_3m = check_3m_pine_signal(ticker_name)
                    if is_valid:
                        row_dict = row.to_dict()
                        row_dict['sl_3m'] = sl_3m
                        row_dict['tp_3m'] = tp_3m
                        valid_rows.append(row_dict)
                df = pd.DataFrame(valid_rows)
        elif label == "🎯 VVV Alert (POC + اختراق)":
            if tv is not None:
                valid_rows = []
                for _, row in df.iterrows():
                    ticker_name = str(row.get('clean_name', row['name'])).strip()
                    is_valid, vvv_data = check_vvv_setup(ticker_name)
                    if is_valid:
                        row_dict = row.to_dict()
                        row_dict.update(vvv_data)
                        valid_rows.append(row_dict)
                df = pd.DataFrame(valid_rows)
            else:
                df = pd.DataFrame()

        if df.empty:
            continue

        results = []
        for _, row in df.iterrows():
            ticker_name = str(row.get('clean_name', row['name'])).strip()
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

            if row.get('has_abcd'):
                stock_lines.append(f"📐 <b>نموذج الهارمونيك:</b> AB=CD مكتمل على فاصل الساعة (1H)")
                stock_lines.append(f"🎯 <b>منطقة الانعكاس PRZ (D):</b> ${row['prz_d']:.4f} | <b>نسبة BC:</b> {row['bc_ratio']:.1f}%")

            if 'vol_1h' in row:
                stock_lines.append(f"⏱️ <b>فوليوم شمعة الساعة:</b> {row['vol_1h']:,}")

            if 'bounce_pct' in row:
                stock_lines.append(f"📈 <b>ارتداد 15M:</b> +{row['bounce_pct']:.2f}% من القاع اللحظي")
                stock_lines.append(f"📊 <b>فوليوم 15M:</b> {row['vol_15m']:,} (تسارع {row['vol_ratio']:.1f}x)")

            if rsi > 0:
                stock_lines.append(f"📉 <b>RSI (1H):</b> {rsi:.1f}")

            stock_lines.append(f"🏢 <b>القطاع:</b> {sector}")
            stock_lines.append(f"💵 <b>السعر:</b> ${price:.4f} | <b>التغير:</b> +{change:.1f}% | Vol: {int(volume):,}")
            stock_lines.append(f"📈 <b>الشارت:</b> <a href='{tv_url}'>TradingView</a>")

            stock_lines.append(f"🎯 <b>الأهداف:</b> ${lvl['t1']:.4f} -&gt; ${lvl['t2']:.4f} -&gt; ${lvl['t3']:.4f}")
            stock_lines.append(f"🛡️ <b>الدعم:</b> ${lvl['support_intraday']:.4f} | ⛔️ <b>الوقف:</b> ${lvl['stop_1']:.4f}")
            if vwap > 0:
                stock_lines.append(f"📊 <b>VWAP:</b> ${vwap:.4f}")
            stock_lines.append("-----------------------------------\n")

            blocks.append("\n".join(stock_lines))

        footer = "\nللفرز فقط، تأكد على الشارت قبل أي قرار."
        send_chunked(header, blocks, footer)

    save_seen(today, counts)


if __name__ == "__main__":
    now_str = datetime.now(RIYADH).strftime("%Y-%m-%d %H:%M:%S")
    print(f"🚀 [{now_str}] بدء جولة فحص الكريبتو عبر GitHub Actions...")

    try:
        main()
        print("✅ اكتملت جولة الفحص بنجاح.")
    except Exception as e:
        print(f"⚠️ حدث خطأ غير متوقع أثناء تنفيذ الجولة: {e}")
        sys.exit(1)
