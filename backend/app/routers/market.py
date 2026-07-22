from fastapi import APIRouter, Query

from app import market_overview as mo

router = APIRouter()


def _bars_to_json(df) -> list[dict]:
    return [
        {
            "timestamp": ts.isoformat(),
            "open": float(o),
            "high": float(h),
            "low": float(l),
            "close": float(c),
            "volume": float(v),
        }
        for ts, o, h, l, c, v in zip(
            df["timestamp"], df["open"], df["high"], df["low"], df["close"], df["volume"]
        )
    ]


@router.get("/status")
def get_status(market: str = Query("US", pattern="^(US|PSX)$")):
    if market == "PSX":
        return mo.psx_market_status()
    return mo.market_status()


@router.get("/quotes")
def get_quotes(symbols: str, crypto: bool = False):
    """symbols: comma-separated list, e.g. AAPL,MSFT,GOOGL"""
    result = {}
    for sym in symbols.split(","):
        sym = sym.strip()
        if sym:
            result[sym] = mo.get_quote(sym, is_crypto=crypto)
    return result


@router.get("/candles")
def get_candles(symbol: str, timeframe: str = "15Min", limit: int = 120, crypto: bool = False):
    if crypto:
        df, is_live = mo.get_crypto_bars(symbol, timeframe, limit)
    else:
        df, is_live = mo.get_bars(symbol, timeframe, limit)
    return {"bars": _bars_to_json(df), "is_live": is_live}


@router.get("/psx/quotes")
def get_psx_quotes(symbols: str):
    snapshot = mo.fetch_psx_snapshot()
    result = {}
    for sym in symbols.split(","):
        sym = sym.strip()
        if sym:
            result[sym] = mo.get_psx_quote(sym, snapshot)
    return result


@router.get("/psx/candles")
def get_psx_candles(symbol: str, limit: int = 120):
    df = mo.fetch_psx_ohlcv(symbol)
    if df is None or len(df) < 10:
        return {"bars": None, "is_live": False}

    df_plot = df.tail(limit).reset_index(drop=True)

    snapshot = mo.fetch_psx_snapshot()
    quote = mo.get_psx_quote(symbol, snapshot)

    return {
        "bars": _bars_to_json(df_plot),
        "is_live": True,
        "live_price": quote["price"],
        "live_chg_pct": quote["chg_pct"],
    }
