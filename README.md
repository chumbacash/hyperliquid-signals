# Chumba Finance Signals

Utilities for fetching Hyperliquid perpetual market data and generating multi-timeframe trading signals using TA-Lib.

## Quick Start

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

   > **Note:** The `TA-Lib` wheel depends on native binaries. On Windows you may need to install the [pre-built library](https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib) before `pip install TA-Lib`.

2. Run the FastAPI server:

   ```bash
   uvicorn main:app --reload
   ```

3. Fetch signals from the API:

   ```bash
   curl "http://127.0.0.1:8000/signals/BTC?timeframes=1d&timeframes=4h"
   ```

   The response includes pre-formatted text suitable for broadcasting (`formatted` field), as well as structured indicator data.

## How It Works

- Historical candles are fetched through the official [Hyperliquid Python SDK](https://github.com/hyperliquid-dex/hyperliquid-python-sdk).
- Indicators (EMA20/50, ADX, DI, MACD, RSI, ATR) are calculated with TA-Lib.
- Price action context (candlestick patterns, support/resistance, volume spikes, higher-timeframe bias) is evaluated alongside indicator signals.
- Trade direction is inferred from trend and momentum, with levels derived from ATR multiples.
- Signals are rendered in a consistent format ready for downstream publishing.

See `hyperliquid/signals.py` for the signal logic and `main.py` for a runnable example.
