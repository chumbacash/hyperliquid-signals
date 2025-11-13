"""Data access layer for Hyperliquid perpetual markets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Dict, Iterable, Optional

import pandas as pd

try:
    from hyperliquid.info import Info  # type: ignore[import]
    from hyperliquid.utils import constants  # type: ignore[import]
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "hyperliquid-python-sdk is required. Install it with 'pip install hyperliquid-python-sdk'."
    ) from exc

DEFAULT_TIMEFRAME = "1h"


@dataclass
class CandleRequest:
    """Parameters describing a candle snapshot request."""

    symbol: str
    timeframe: str = DEFAULT_TIMEFRAME
    end: Optional[datetime] = None
    lookback: int = 250  # number of bars to request

    def interval(self) -> str:
        """Return the Hyperliquid interval string."""
        if self.timeframe not in TIMEFRAME_TO_MINUTES:
            supported = ", ".join(sorted(TIMEFRAME_TO_MINUTES))
            raise ValueError(f"Unsupported timeframe '{self.timeframe}'. Supported: {supported}")
        return self.timeframe

    def end_time(self) -> datetime:
        return self.end or datetime.now(tz=UTC)

    def start_time(self) -> datetime:
        minutes = TIMEFRAME_TO_MINUTES[self.timeframe]
        delta = timedelta(minutes=minutes * self.lookback)
        return self.end_time() - delta


TIMEFRAME_TO_MINUTES: Dict[str, int] = {
    "15m": 15,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}


class HyperliquidDataClient:
    """Thin wrapper around the Hyperliquid Info SDK for fetching historical candles."""

    def __init__(self, info: Info) -> None:
        self._info = info

    @property
    def info(self) -> Info:
        return self._info

    def fetch_candles(self, request: CandleRequest) -> pd.DataFrame:
        """Fetch OHLCV candles and return them as a pandas DataFrame."""
        interval = request.interval()
        end_ts = int(request.end_time().timestamp() * 1000)
        start_ts = int(request.start_time().timestamp() * 1000)
        payload = self._info.candles_snapshot(
            request.symbol,
            interval,
            start_ts,
            end_ts,
        )
        candles = _normalize_candles(payload)
        if candles.empty:
            raise RuntimeError(
                f"No candle data returned for {request.symbol} at interval {interval} "
                f"between {request.start_time()} and {request.end_time()}"
            )
        return candles


def _normalize_candles(raw: Iterable[dict]) -> pd.DataFrame:
    """Convert candle snapshot data into a typed DataFrame."""
    records = list(raw)
    if not records:
        return pd.DataFrame()

    frame = pd.DataFrame(records)
    frame["time"] = pd.to_datetime(frame["t"], unit="ms", utc=True)
    frame = frame.set_index("time").sort_index()

    for column in ("o", "h", "l", "c", "v"):
        frame[column] = frame[column].astype(float)

    frame = frame.rename(
        columns={
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
        }
    )
    return frame[["open", "high", "low", "close", "volume"]]


def build_default_client(base_url: Optional[str] = None, skip_ws: bool = True) -> HyperliquidDataClient:
    """Convenience builder that points at mainnet by default."""
    target = base_url or constants.MAINNET_API_URL
    info = Info(target, skip_ws=skip_ws)
    return HyperliquidDataClient(info)
