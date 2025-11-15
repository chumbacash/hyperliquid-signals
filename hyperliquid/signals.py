"""Signal generation utilities built on top of Hyperliquid data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import talib  # type: ignore[import]
except ImportError as exc:  # pragma: no cover
    raise ImportError("TA-Lib is required. Install it with 'pip install TA-Lib'.") from exc

from .data import CandleRequest, HyperliquidDataClient

Direction = Literal["Long", "Short"]


@dataclass
class SignalPayload:
    """Structured representation of a trading signal."""

    symbol: str
    timeframe: str
    direction: Direction
    entry: Tuple[float, float]
    targets: List[float]
    stop_loss: float
    indicators: Dict[str, float]
    generated_at: datetime
    confidence: float = 0.0
    price_action: Optional[Dict[str, Any]] = None
    price_history: Optional[List[float]] = None

    def format(self) -> str:
        """Return a human-readable representation of the signal."""
        arrow = "🟢" if self.direction == "Long" else "🔴"
        lightning = "⚡"
        calendar = "📅"
        header = f"{arrow} {lightning} {calendar} {self.symbol} (PERP - {self.timeframe.upper()})"
        body_lines = [
            f"{self.direction} Signal",
            f"- Entry: {self.entry[0]:.6f} - {self.entry[1]:.6f}",
            f"- Targets: TP1: {self.targets[0]:.6f}, TP2: {self.targets[1]:.6f}, TP3: {self.targets[2]:.6f}",
            f"- Stop Loss: {self.stop_loss:.6f}",
            "",
            f"Analysis: {self._analysis_summary()}",
        ]
        if self.price_action:
            summary = self.price_action.get("summary")
            if summary:
                body_lines.extend(["", f"Price Action: {summary}"])

        body_lines.extend(
            [
                "",
                f"Signal generated at {self.generated_at.strftime('%H:%M')} UTC",
            ]
        )
        return "\n".join([header, "", *body_lines])

    def _analysis_summary(self) -> str:
        ema20 = self.indicators["ema20"]
        ema50 = self.indicators["ema50"]
        adx = self.indicators["adx"]
        plus_di = self.indicators["plus_di"]
        minus_di = self.indicators["minus_di"]
        macd_hist = self.indicators["macd_hist"]
        rsi = self.indicators["rsi"]
        atr = self.indicators["atr"]

        trend_direction = "up" if ema20 > ema50 else "down"
        trend_clause = f"Trend {trend_direction}: EMA20 {ema20:.2f} {'>' if ema20 > ema50 else '<'} EMA50 {ema50:.2f}"
        adx_clause = f"ADX {adx:.1f}, +DI {plus_di:.1f} { '>' if plus_di > minus_di else '<' } -DI {minus_di:.1f}"
        momentum_clause = "Momentum: MACD hist rising" if macd_hist > 0 else "Momentum: MACD hist falling"
        rsi_clause = f"RSI {rsi:.1f}"
        atr_clause = f"ATR {atr:.3f}"

        return "; ".join([trend_clause, adx_clause, momentum_clause, rsi_clause, atr_clause])

    def to_dict(self) -> Dict[str, object]:
        """Serialize the signal payload to a JSON-friendly dictionary."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "entry": {"lower": self.entry[0], "upper": self.entry[1]},
            "targets": self.targets,
            "stopLoss": self.stop_loss,
            "indicators": self.indicators,
            "generatedAt": self.generated_at.isoformat(),
            "formatted": self.format(),
            "confidence": self.confidence,
            "priceAction": self.price_action,
            "priceHistory": self.price_history,
        }


class SignalGenerator:
    """Generate trading signals for Hyperliquid perpetuals using TA-Lib indicators."""

    def __init__(self, client: HyperliquidDataClient) -> None:
        self._client = client

    def generate(
        self,
        symbol: str,
        timeframe: str,
        lookback: int = 250,
        as_of: Optional[datetime] = None,
    ) -> SignalPayload:
        """Generate a trading signal for the given symbol and timeframe."""
        request = CandleRequest(symbol=symbol, timeframe=timeframe, end=as_of, lookback=lookback)
        candles = self._client.fetch_candles(request)
        indicators = compute_indicators(candles)
        direction = classify_direction(indicators)
        confidence = calculate_confidence(indicators, direction)
        levels = build_trade_levels(candles, indicators, direction)
        generated_at = (as_of or datetime.now(tz=UTC)).replace(second=0, microsecond=0)
        higher_timeframe = _maybe_fetch_higher_timeframe(self._client, symbol, timeframe, as_of)
        price_action = analyze_price_action(candles, timeframe, higher_timeframe)
        price_history = candles["close"].astype(float).tail(100).tolist()
        return SignalPayload(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            entry=levels["entry"],
            targets=levels["targets"],
            stop_loss=levels["stop_loss"],
            indicators=indicators,
            generated_at=generated_at,
            confidence=confidence,
            price_action=price_action,
            price_history=price_history,
        )


def compute_indicators(candles: pd.DataFrame) -> Dict[str, float]:
    """Compute TA-Lib indicators used in the signal logic."""
    closes = candles["close"].astype(float).values
    highs = candles["high"].astype(float).values
    lows = candles["low"].astype(float).values

    ema20 = talib.EMA(closes, timeperiod=20)
    ema50 = talib.EMA(closes, timeperiod=50)
    adx = talib.ADX(highs, lows, closes, timeperiod=14)
    plus_di = talib.PLUS_DI(highs, lows, closes, timeperiod=14)
    minus_di = talib.MINUS_DI(highs, lows, closes, timeperiod=14)
    macd, macd_signal, macd_hist = talib.MACD(closes, fastperiod=12, slowperiod=26, signalperiod=9)
    rsi = talib.RSI(closes, timeperiod=14)
    atr = talib.ATR(highs, lows, closes, timeperiod=14)

    return {
        "ema20": _latest_valid(ema20),
        "ema50": _latest_valid(ema50),
        "adx": _latest_valid(adx),
        "plus_di": _latest_valid(plus_di),
        "minus_di": _latest_valid(minus_di),
        "macd": _latest_valid(macd),
        "macd_signal": _latest_valid(macd_signal),
        "macd_hist": _latest_valid(macd_hist),
        "rsi": _latest_valid(rsi),
        "atr": _latest_valid(atr),
        "close": candles["close"].astype(float).iloc[-1],
    }


def classify_direction(indicators: Dict[str, float]) -> Direction:
    """Determine whether market bias is long or short."""
    ema20 = indicators["ema20"]
    ema50 = indicators["ema50"]
    macd_hist = indicators["macd_hist"]
    rsi = indicators["rsi"]

    if ema20 > ema50 and macd_hist >= 0 and rsi >= 45:
        return "Long"
    if ema20 < ema50 and macd_hist <= 0 and rsi <= 55:
        return "Short"
    # fallback to trend direction
    return "Long" if ema20 >= ema50 else "Short"


def calculate_confidence(indicators: Dict[str, float], direction: Direction) -> float:
    """Calculate signal confidence score (0-100) based on indicator alignment."""
    score = 0.0
    
    ema20 = indicators["ema20"]
    ema50 = indicators["ema50"]
    adx = indicators["adx"]
    plus_di = indicators["plus_di"]
    minus_di = indicators["minus_di"]
    macd_hist = indicators["macd_hist"]
    rsi = indicators["rsi"]
    close = indicators["close"]
    
    if direction == "Long":
        # Trend alignment (30 points)
        if ema20 > ema50:
            score += 15
            if close > ema20:
                score += 15
        
        # Momentum (25 points)
        if macd_hist > 0:
            score += 15
        if plus_di > minus_di:
            score += 10
        
        # RSI (20 points)
        if 45 <= rsi <= 70:
            score += 20
        elif 40 <= rsi < 45 or 70 < rsi <= 75:
            score += 10
        
        # Trend strength (25 points)
        if adx >= 25:
            score += 25
        elif adx >= 20:
            score += 15
        elif adx >= 15:
            score += 10
    
    else:  # Short
        # Trend alignment (30 points)
        if ema20 < ema50:
            score += 15
            if close < ema20:
                score += 15
        
        # Momentum (25 points)
        if macd_hist < 0:
            score += 15
        if minus_di > plus_di:
            score += 10
        
        # RSI (20 points)
        if 30 <= rsi <= 55:
            score += 20
        elif 25 <= rsi < 30 or 55 < rsi <= 60:
            score += 10
        
        # Trend strength (25 points)
        if adx >= 25:
            score += 25
        elif adx >= 20:
            score += 15
        elif adx >= 15:
            score += 10
    
    return min(100.0, max(0.0, score))


def build_trade_levels(
    candles: pd.DataFrame,
    indicators: Dict[str, float],
    direction: Direction,
) -> Dict[str, object]:
    """Construct entry, targets and stop levels using ATR multiples."""
    close_price = indicators["close"]
    atr = indicators["atr"]

    buffer = atr * 0.15
    target_multipliers = np.array([1.0, 2.0, 3.0])
    stop_multiplier = 2.5

    if direction == "Long":
        entry = (close_price - buffer, close_price + buffer)
        targets = close_price + atr * target_multipliers
        stop_loss = close_price - atr * stop_multiplier
    else:
        entry = (close_price - buffer, close_price + buffer)
        targets = close_price - atr * target_multipliers
        stop_loss = close_price + atr * stop_multiplier

    return {
        "entry": entry,
        "targets": targets.tolist(),
        "stop_loss": stop_loss,
    }


def _latest_valid(series: Iterable[float]) -> float:
    arr = np.asarray(series, dtype=float)
    arr = arr[~np.isnan(arr)]
    if not len(arr):
        raise ValueError("Indicator series contains only NaN values")
    return float(arr[-1])


def analyze_price_action(
    candles: pd.DataFrame,
    timeframe: str,
    higher_timeframe: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """Summarize short-term price action context for the latest bars."""
    pattern = _detect_pattern(candles)
    support, resistance = _nearest_levels(candles)
    volume_ratio = _volume_ratio(candles)
    structure = _determine_trend(candles)
    higher_structure = _determine_trend(higher_timeframe) if higher_timeframe is not None else None

    summary_bits: List[str] = []
    if pattern:
        summary_bits.append(f"{pattern['bias']} via {pattern['name']}")
    else:
        summary_bits.append("No dominant candlestick pattern")

    if structure and structure != "range":
        summary_bits.append(f"{timeframe.upper()} structure {structure}")

    if higher_structure:
        summary_bits.append(f"Higher TF bias {higher_structure}")

    if support:
        summary_bits.append(f"Support ~{support:.2f}")
    if resistance:
        summary_bits.append(f"Resistance ~{resistance:.2f}")

    if volume_ratio >= 1.3:
        summary_bits.append(f"Volume spike x{volume_ratio:.2f}")

    summary = "; ".join(summary_bits)

    return {
        "pattern": pattern,
        "support": support,
        "resistance": resistance,
        "volumeRatio": volume_ratio,
        "timeframeTrend": structure,
        "higherTimeframeTrend": higher_structure,
        "summary": summary,
    }


def _maybe_fetch_higher_timeframe(
    client: HyperliquidDataClient,
    symbol: str,
    timeframe: str,
    as_of: Optional[datetime],
) -> Optional[pd.DataFrame]:
    higher_map = {
        "15m": "1h",
        "1h": "4h",
        "4h": "1d",
    }
    higher_tf = higher_map.get(timeframe)
    if higher_tf is None:
        return None
    try:
        return client.fetch_candles(CandleRequest(symbol=symbol, timeframe=higher_tf, end=as_of, lookback=120))
    except Exception:
        return None


def _detect_pattern(candles: pd.DataFrame) -> Optional[Dict[str, Any]]:
    if len(candles) < 3:
        return None

    last = candles.iloc[-1]
    prev = candles.iloc[-2]

    if _is_three_white_soldiers(candles):
        return {"name": "Three White Soldiers", "bias": "Long", "confidence": "high", "candleCount": 3}
    if _is_three_black_crows(candles):
        return {"name": "Three Black Crows", "bias": "Short", "confidence": "high", "candleCount": 3}
    if _is_bullish_engulfing(prev, last):
        return {"name": "Bullish Engulfing", "bias": "Long", "confidence": "medium", "candleCount": 2}
    if _is_bearish_engulfing(prev, last):
        return {"name": "Bearish Engulfing", "bias": "Short", "confidence": "medium", "candleCount": 2}
    if _is_bullish_pin_bar(last):
        return {"name": "Hammer (Pin Bar)", "bias": "Long", "confidence": "medium", "candleCount": 1}
    if _is_bearish_pin_bar(last):
        return {"name": "Shooting Star (Pin Bar)", "bias": "Short", "confidence": "medium", "candleCount": 1}
    if _is_inside_bar(prev, last):
        return {"name": "Inside Bar", "bias": "Breakout", "confidence": "neutral", "candleCount": 2}
    if _is_doji(last):
        return {"name": "Doji", "bias": "Neutral", "confidence": "low", "candleCount": 1}
    return None


def _candle_color(candle: pd.Series) -> str:
    return "green" if candle["close"] >= candle["open"] else "red"


def _is_three_white_soldiers(candles: pd.DataFrame) -> bool:
    last_three = candles.iloc[-3:]
    colors = [_candle_color(row) for _, row in last_three.iterrows()]
    if not all(color == "green" for color in colors):
        return False
    opens = last_three["open"].values
    closes = last_three["close"].values
    return np.all(np.diff(opens) > 0) and np.all(np.diff(closes) > 0)


def _is_three_black_crows(candles: pd.DataFrame) -> bool:
    last_three = candles.iloc[-3:]
    colors = [_candle_color(row) for _, row in last_three.iterrows()]
    if not all(color == "red" for color in colors):
        return False
    opens = last_three["open"].values
    closes = last_three["close"].values
    return np.all(np.diff(opens) < 0) and np.all(np.diff(closes) < 0)


def _is_bullish_engulfing(prev: pd.Series, last: pd.Series) -> bool:
    return (
        _candle_color(prev) == "red"
        and _candle_color(last) == "green"
        and last["open"] <= prev["close"]
        and last["close"] >= prev["open"]
    )


def _is_bearish_engulfing(prev: pd.Series, last: pd.Series) -> bool:
    return (
        _candle_color(prev) == "green"
        and _candle_color(last) == "red"
        and last["open"] >= prev["close"]
        and last["close"] <= prev["open"]
    )


def _is_bullish_pin_bar(candle: pd.Series) -> bool:
    body = abs(candle["close"] - candle["open"])
    total = candle["high"] - candle["low"]
    if total == 0:
        return False
    lower_wick = min(candle["open"], candle["close"]) - candle["low"]
    upper_wick = candle["high"] - max(candle["open"], candle["close"])
    return (
        _candle_color(candle) == "green"
        and lower_wick >= total * 0.5
        and lower_wick >= body * 2
        and upper_wick <= total * 0.3
    )


def _is_bearish_pin_bar(candle: pd.Series) -> bool:
    body = abs(candle["close"] - candle["open"])
    total = candle["high"] - candle["low"]
    if total == 0:
        return False
    lower_wick = min(candle["open"], candle["close"]) - candle["low"]
    upper_wick = candle["high"] - max(candle["open"], candle["close"])
    return (
        _candle_color(candle) == "red"
        and upper_wick >= total * 0.5
        and upper_wick >= body * 2
        and lower_wick <= total * 0.3
    )


def _is_inside_bar(prev: pd.Series, last: pd.Series) -> bool:
    return last["high"] <= prev["high"] and last["low"] >= prev["low"]


def _is_doji(candle: pd.Series) -> bool:
    body = abs(candle["close"] - candle["open"])
    total = candle["high"] - candle["low"]
    if total == 0:
        return False
    return body <= total * 0.1


def _nearest_levels(candles: pd.DataFrame, lookback: int = 60) -> Tuple[Optional[float], Optional[float]]:
    window = candles.tail(lookback)
    price = float(window["close"].iloc[-1])

    supports = window.loc[window["low"] < price, "low"]
    support = float(supports.max()) if not supports.empty else None

    resistances = window.loc[window["high"] > price, "high"]
    resistance = float(resistances.min()) if not resistances.empty else None

    return support, resistance


def _volume_ratio(candles: pd.DataFrame, period: int = 20) -> float:
    volumes = candles["volume"].astype(float)
    last = float(volumes.iloc[-1])
    if len(volumes) <= 1:
        return 1.0
    baseline = float(volumes.tail(period + 1).iloc[:-1].mean()) if len(volumes) > period else float(volumes.iloc[:-1].mean())
    baseline = max(baseline, 1e-9)
    return last / baseline


def _determine_trend(candles: Optional[pd.DataFrame], lookback: int = 40) -> Optional[str]:
    if candles is None or candles.empty:
        return None
    closes = candles["close"].astype(float).tail(lookback)
    if len(closes) < 5:
        return "range"
    delta = closes.iloc[-1] - closes.iloc[0]
    pct_change = delta / closes.iloc[0] if closes.iloc[0] != 0 else 0.0
    threshold = 0.001
    if pct_change > threshold:
        return "uptrend"
    if pct_change < -threshold:
        return "downtrend"
    return "range"

