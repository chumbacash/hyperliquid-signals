"""FastAPI entrypoint exposing Hyperliquid perp signal endpoints."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from hyperliquid import SignalGenerator, build_default_client
from hyperliquid.data import TIMEFRAME_TO_MINUTES

DEFAULT_TIMEFRAMES: List[str] = ["1d", "4h", "1h", "15m"]
DEFAULT_SYMBOLS: List[str] = ["BTC"]

app = FastAPI(title="Chumba Finance Signal API", version="0.1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """Serve the trading signals dashboard."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "default_symbols_input": ",".join(DEFAULT_SYMBOLS),
            "default_symbols_list": DEFAULT_SYMBOLS,
            "default_timeframes": DEFAULT_TIMEFRAMES,
        },
    )


def _validate_timeframes(timeframes: List[str]) -> None:
    invalid = [tf for tf in timeframes if tf not in TIMEFRAME_TO_MINUTES]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframes: {', '.join(invalid)}")


def _generate_for_symbol(
    generator: SignalGenerator,
    symbol: str,
    timeframes: List[str],
) -> List[Dict[str, object]]:
    try:
        return [generator.generate(symbol.upper(), timeframe).to_dict() for timeframe in timeframes]
    except Exception as exc:  # pragma: no cover - bubbled runtime errors
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/signals")
def get_signals_multi(
    symbols: List[str] = Query(DEFAULT_SYMBOLS, description="Symbols to evaluate"),
    timeframes: List[str] = Query(DEFAULT_TIMEFRAMES, description="Timeframes to evaluate"),
    api_url: Optional[str] = None,
) -> dict:
    if not symbols:
        raise HTTPException(status_code=400, detail="At least one symbol must be provided")

    _validate_timeframes(timeframes)

    generator = get_generator(api_url=api_url)
    payload = {
        symbol.upper(): _generate_for_symbol(generator, symbol, timeframes)
        for symbol in symbols
    }
    return {
        "symbols": payload,
        "timeframes": timeframes,
    }


@app.get("/signals/{symbol}")
def get_signals(
    symbol: str,
    timeframes: List[str] = Query(DEFAULT_TIMEFRAMES, description="Timeframes to evaluate"),
    api_url: Optional[str] = None,
) -> dict:
    _validate_timeframes(timeframes)
    generator = get_generator(api_url=api_url)
    results = _generate_for_symbol(generator, symbol, timeframes)
    return {
        "symbol": symbol.upper(),
        "timeframes": timeframes,
        "signals": results,
    }
