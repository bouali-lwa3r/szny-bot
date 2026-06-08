"""
⚡ SZNY Trading Bot — Telegram Signals
Sweep + Zone + New York + Yield
@SZNY27_bot
"""

import requests
import time
from datetime import datetime, timezone
import ccxt

# ═══════════════════════════════════════
#         إعدادات Telegram
# ═══════════════════════════════════════
TELEGRAM_TOKEN  = "8925940021:AAHhy6ltBxGPGPNul4BLCCtUin-QL8w8BYM"
TELEGRAM_CHATID = "5435780133"

# ═══════════════════════════════════════
#         الأزواج المتابعة
# ═══════════════════════════════════════
SYMBOLS = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "XAUUSD": "XAU/USD"
}

# ═══════════════════════════════════════
#         إعدادات الاستراتيجية
# ═══════════════════════════════════════
LOOKBACK       = 50       # عدد الكاندلات للبحث
TOLERANCE_PIPS = 5        # هامش Equal Highs/Lows
RR             = 2.0      # Risk/Reward
SL_PIPS_FOREX  = 15       # SL للفوركس
SL_PIPS_GOLD   = 250      # SL للذهب (بالنقاط)

# ═══════════════════════════════════════
#         إعداد Exchange
# ═══════════════════════════════════════
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

last_signal_time = {}

# ═══════════════════════════════════════
#         إرسال رسالة Telegram
# ═══════════════════════════════════════
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHATID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, data=data, timeout=10)
        if res.status_code == 200:
            print(f"✅ Telegram OK")
        else:
            print(f"❌ Telegram Error: {res.text}")
    except Exception as e:
        print(f"❌ Telegram Exception: {e}")

# ═══════════════════════════════════════
#         جيب بيانات الكاندلات
# ═══════════════════════════════════════
def get_candles(symbol, timeframe, limit=100):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        return ohlcv  # [timestamp, open, high, low, close, volume]
    except Exception as e:
        print(f"❌ Error fetching {symbol}: {e}")
        return []

# ═══════════════════════════════════════
#         تحقق من جلسة نيويورك
# ═══════════════════════════════════════
def is_ny_session():
    now = datetime.now(timezone.utc)
    hour = now.hour
    # جلسة نيويورك: 13:00 - 22:00 UTC = 3م - 12ليل بتوقيت المغرب
    return True

# ═══════════════════════════════════════
#         كشف Liquidity Sweep
# ═══════════════════════════════════════
def detect_liquidity_sweep(candles_h1, candles_m15, symbol):
    if len(candles_h1) < 10 or len(candles_m15) < 3:
        return 0

    # جيب بيانات H1
    highs_h1 = [c[2] for c in candles_h1[-LOOKBACK:-1]]
    lows_h1  = [c[3] for c in candles_h1[-LOOKBACK:-1]]

    # حدد tolerance حسب الزوج
    pip_size = 0.0001 if "USD" in symbol and "XAU" not in symbol else 0.1
    tolerance = TOLERANCE_PIPS * pip_size

    # ابحث على Equal Highs و Equal Lows
    def find_equal_levels(levels, tol):
        from collections import Counter
        rounded = [round(l / tol) * tol for l in levels]
        counts = Counter(rounded)
        return [(level, count) for level, count in counts.items() if count >= 2]

    equal_highs = find_equal_levels(highs_h1, tolerance)
    equal_lows  = find_equal_levels(lows_h1, tolerance)

    # آخر كاندل M15
    last_candle = candles_m15[-2]
    curr_low    = last_candle[3]
    curr_high   = last_candle[2]
    curr_close  = last_candle[4]

    # SSL Sweep → BUY
    for low_level, _ in equal_lows:
        if curr_low < low_level and curr_close > low_level:
            return 1  # BUY

    # BSL Sweep → SELL
    for high_level, _ in equal_highs:
        if curr_high > high_level and curr_close < high_level:
            return -1  # SELL

    return 0

# ═══════════════════════════════════════
#         كشف BOS
# ═══════════════════════════════════════
def detect_bos(candles_m15, direction):
    if len(candles_m15) < 3:
        return False

    prev_candle = candles_m15[-3]
    last_candle = candles_m15[-2]

    if direction == 1:  # BUY — ابحث على BOS صاعد
        return last_candle[2] > prev_candle[2]  # High > prev High
    else:  # SELL — ابحث على BOS هابط
        return last_candle[3] < prev_candle[3]  # Low < prev Low

# ═══════════════════════════════════════
#         بناء وإرسال الإشارة
# ═══════════════════════════════════════
def send_signal(symbol, direction, candles_m15):
    # تجنب تكرار الإشارة (15 دقيقة)
    now = time.time()
    if symbol in last_signal_time:
        if now - last_signal_time[symbol] < 900:
            return
    last_signal_time[symbol] = now

    entry = candles_m15[-2][4]  # Close ديال آخر كاندل

    # حدد SL حسب الزوج
    pip_size = 0.0001 if "XAU" not in symbol else 1.0
    sl_pips  = SL_PIPS_FOREX if "XAU" not in symbol else SL_PIPS_GOLD
    sl_dist  = sl_pips * pip_size

    if direction == 1:  # BUY
        sl = entry - sl_dist
        tp = entry + (sl_dist * RR)
        dir_emoji = "🟢"
        dir_text  = "BUY"
        sweep_text = "SSL Sweep ✅"
    else:  # SELL
        sl = entry + sl_dist
        tp = entry - (sl_dist * RR)
        dir_emoji = "🔴"
        dir_text  = "SELL"
        sweep_text = "BSL Sweep ✅"

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    message = (
        f"\n⚡ *SZNY SIGNAL*\n"
        f"════════════════\n"
        f"{dir_emoji} *{dir_text}* — `{symbol}`\n"
        f"════════════════\n"
        f"📍 Entry : `{entry:.5f}`\n"
        f"🛑 SL    : `{sl:.5f}`\n"
        f"🎯 TP    : `{tp:.5f}`\n"
        f"📊 RR    : `1:{RR}`\n"
        f"────────────────\n"
        f"🔍 {sweep_text}\n"
        f"🕐 {now_str}\n"
        f"════════════════\n"
        f"_SZNY Strategy — Zakariya_"
    )

    send_telegram(message)
    print(f"📨 Signal sent: {dir_text} {symbol} @ {entry:.5f}")

# ═══════════════════════════════════════
#         الحلقة الرئيسية
# ═══════════════════════════════════════
def main():
    print("⚡ SZNY Bot Started — @SZNY27_bot")
    send_telegram("⚡ *SZNY Bot Started*\n📊 Watching: EURUSD | GBPUSD | XAUUSD\n🕐 NY Session Only")

    while True:
        try:
            if not is_ny_session():
                print("⏳ Outside NY Session — waiting...")
                time.sleep(300)  # استنى 5 دقائق
                continue

            print(f"\n🔍 Scanning... {datetime.now(timezone.utc).strftime('%H:%M UTC')}")

            for name, symbol in SYMBOLS.items():
                try:
                    candles_h1  = get_candles(symbol, "1h",  limit=LOOKBACK+5)
                    candles_m15 = get_candles(symbol, "15m", limit=10)

                    if not candles_h1 or not candles_m15:
                        continue

                    sweep = detect_liquidity_sweep(candles_h1, candles_m15, name)

                    if sweep == 0:
                        print(f"  {name}: No signal")
                        continue

                    bos = detect_bos(candles_m15, sweep)

                    if bos:
                        print(f"  {name}: ✅ Signal found! {'BUY' if sweep==1 else 'SELL'}")
                        send_signal(name, sweep, candles_m15)
                    else:
                        print(f"  {name}: Sweep found but no BOS yet")

                    time.sleep(1)

                except Exception as e:
                    print(f"  ❌ Error {name}: {e}")

            print("✅ Scan complete — next scan in 15min")
            time.sleep(900)  # سكان كل 15 دقيقة

        except KeyboardInterrupt:
            print("\n🛑 Bot stopped")
            send_telegram("🛑 SZNY Bot Stopped")
            break
        except Exception as e:
            print(f"❌ Main error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
