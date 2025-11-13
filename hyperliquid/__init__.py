"""Core utilities for interacting with the Hyperliquid API and generating signals."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path

# Ensure the official SDK package is discoverable for submodule imports.
try:
    _sdk_dist = metadata.distribution("hyperliquid-python-sdk")
except metadata.PackageNotFoundError:  # pragma: no cover - optional dependency at runtime
    _sdk_dist = None

if _sdk_dist is not None:
    _sdk_path = Path(_sdk_dist.locate_file("hyperliquid"))
    if _sdk_path.exists():
        _sdk_path_str = str(_sdk_path)
        if _sdk_path_str not in __path__:
            __path__.insert(0, _sdk_path_str)

from .data import HyperliquidDataClient, build_default_client
from .signals import SignalGenerator, SignalPayload

__all__ = [
    "HyperliquidDataClient",
    "SignalGenerator",
    "SignalPayload",
    "build_default_client",
]
