"""FastAPI entrypoint exposing Hyperliquid perp signal endpoints."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from hyperliquid import SignalGenerator, build_default_client
from hyperliquid.data import TIMEFRAME_TO_MINUTES

DEFAULT_TIMEFRAMES: List[str] = ["1d", "4h", "1h", "15m"]
DEFAULT_SYMBOLS: List[str] = ["BTC"]

# Thread pool for parallel signal generation
executor = ThreadPoolExecutor(max_workers=4)

# Simple in-memory cache with TTL
signal_cache: Dict[str, tuple[dict, datetime]] = {}
CACHE_TTL_MINUTES = 5

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


def _generate_single_signal(
    generator: SignalGenerator,
    symbol: str,
    timeframe: str,
) -> Dict[str, object]:
    """Generate a single signal (used for parallel execution)."""
    return generator.generate(symbol.upper(), timeframe).to_dict()


def _get_cache_key(symbol: str, timeframe: str) -> str:
    """Generate cache key for a signal."""
    return f"{symbol.upper()}:{timeframe}"


def _get_cached_signal(symbol: str, timeframe: str) -> Optional[Dict[str, object]]:
    """Get signal from cache if not expired."""
    cache_key = _get_cache_key(symbol, timeframe)
    if cache_key in signal_cache:
        signal, cached_at = signal_cache[cache_key]
        if datetime.now() - cached_at < timedelta(minutes=CACHE_TTL_MINUTES):
            return signal
        else:
            # Remove expired entry
            del signal_cache[cache_key]
    return None


def _cache_signal(symbol: str, timeframe: str, signal: Dict[str, object]) -> None:
    """Store signal in cache."""
    cache_key = _get_cache_key(symbol, timeframe)
    signal_cache[cache_key] = (signal, datetime.now())


async def _generate_for_symbol_parallel(
    generator: SignalGenerator,
    symbol: str,
    timeframes: List[str],
) -> List[Dict[str, object]]:
    """Generate signals for all timeframes in parallel with caching."""
    results = []
    tasks_to_run = []
    
    # Check cache first
    for timeframe in timeframes:
        cached = _get_cached_signal(symbol, timeframe)
        if cached:
            results.append((timeframe, cached))
        else:
            tasks_to_run.append(timeframe)
    
    # Generate missing signals in parallel
    if tasks_to_run:
        loop = asyncio.get_event_loop()
        futures = [
            loop.run_in_executor(
                executor,
                _generate_single_signal,
                generator,
                symbol,
                tf
            )
            for tf in tasks_to_run
        ]
        
        try:
            generated = await asyncio.gather(*futures)
            for tf, signal in zip(tasks_to_run, generated):
                _cache_signal(symbol, tf, signal)
                results.append((tf, signal))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    
    # Sort by original timeframe order
    timeframe_order = {tf: i for i, tf in enumerate(timeframes)}
    results.sort(key=lambda x: timeframe_order[x[0]])
    
    return [signal for _, signal in results]


@app.get("/signals")
async def get_signals_multi(
    symbols: List[str] = Query(DEFAULT_SYMBOLS, description="Symbols to evaluate"),
    timeframes: List[str] = Query(DEFAULT_TIMEFRAMES, description="Timeframes to evaluate"),
    api_url: Optional[str] = None,
) -> dict:
    if not symbols:
        raise HTTPException(status_code=400, detail="At least one symbol must be provided")

    _validate_timeframes(timeframes)

    generator = get_generator(api_url=api_url)
    
    # Generate all symbols in parallel
    symbol_tasks = [
        _generate_for_symbol_parallel(generator, symbol, timeframes)
        for symbol in symbols
    ]
    
    all_results = await asyncio.gather(*symbol_tasks)
    
    payload = {
        symbol.upper(): results
        for symbol, results in zip(symbols, all_results)
    }
    
    return {
        "symbols": payload,
        "timeframes": timeframes,
    }


@app.get("/signals/{symbol}")
async def get_signals(
    symbol: str,
    timeframes: List[str] = Query(DEFAULT_TIMEFRAMES, description="Timeframes to evaluate"),
    api_url: Optional[str] = None,
) -> dict:
    _validate_timeframes(timeframes)
    generator = get_generator(api_url=api_url)
    results = await _generate_for_symbol_parallel(generator, symbol, timeframes)
    return {
        "symbol": symbol.upper(),
        "timeframes": timeframes,
        "signals": results,
    }


@app.get("/cache/stats")
def cache_stats() -> dict:
    """Get cache statistics."""
    now = datetime.now()
    valid_entries = sum(
        1 for _, (_, cached_at) in signal_cache.items()
        if now - cached_at < timedelta(minutes=CACHE_TTL_MINUTES)
    )
    return {
        "total_entries": len(signal_cache),
        "valid_entries": valid_entries,
        "ttl_minutes": CACHE_TTL_MINUTES,
    }


@app.post("/cache/clear")
def clear_cache() -> dict:
    """Clear the signal cache."""
    signal_cache.clear()
    return {"status": "cache cleared"}
