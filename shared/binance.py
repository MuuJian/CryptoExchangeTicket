"""Binance symbol helpers shared by watchlists and realtime OI."""

from __future__ import annotations


TRADINGVIEW_SYMBOL_MAP = {
    "币安人生USDT": "BIANRENSHENGUSDT",
    "龙虾USDT": "LONGXIAUSDT",
    "我踏马来了USDT": "WOTAMALAILIAOUSDT",
}


def is_valid_binance_symbol(value: object) -> bool:
    """Return whether *value* contains only Binance symbol characters."""
    return isinstance(value, str) and value.isalnum()
