"""FastAPI entrypoint exposing Hyperliquid perp signal endpoints."""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from hyperliquid import SignalGenerator, build_default_client
from hyperliquid.data import TIMEFRAME_TO_MINUTES

DEFAULT_TIMEFRAMES: List[str] = ["1d", "4h", "1h", "15m"]

app = FastAPI(title="Chumba Finance Signal API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_generator(api_url: Optional[str] = None) -> SignalGenerator:
    client = build_default_client(base_url=api_url)
    return SignalGenerator(client)


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}


@app.get("/signals/{symbol}")
def get_signals(
    symbol: str,
    timeframes: List[str] = Query(DEFAULT_TIMEFRAMES, description="Timeframes to evaluate"),
    api_url: Optional[str] = None,
) -> dict:
    invalid = [tf for tf in timeframes if tf not in TIMEFRAME_TO_MINUTES]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframes: {', '.join(invalid)}")

    generator = get_generator(api_url=api_url)

    try:
        results = [generator.generate(symbol.upper(), timeframe) for timeframe in timeframes]
    except Exception as exc:  # pragma: no cover - bubbled runtime errors
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "symbol": symbol.upper(),
        "timeframes": timeframes,
        "signals": [signal.to_dict() for signal in results],
    }
