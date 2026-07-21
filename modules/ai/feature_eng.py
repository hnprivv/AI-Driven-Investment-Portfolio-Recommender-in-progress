"""
Feature Engineering for AIPRS PPO Advisory Agent
=================================================
Computes 16 technical indicator features from OHLCV DataFrames.
Handles train-time normalizer fitting and inference-time transformation.
"""
from __future__ import annotations

import os
import pickle
import numpy as np
import pandas as pd

# ── Feature / user profile metadata ─────────────────────────────────────────

FEATURE_NAMES = [
    "log_ret_1", "log_ret_5", "log_ret_20",   # price momentum
    "rsi_14",                                   # oscillator
    "macd_hist_norm",                           # trend
    "bb_pos",                                   # mean-reversion band position
    "ema_ratio_short",                          # EMA9 / EMA21 – 1
    "ema_ratio_long",                           # EMA21 / EMA50 – 1
    "vol_10", "vol_20",                         # realised volatility
    "price_vs_sma20",                           # price relative to moving average
    "volume_ratio",                             # volume anomaly
    "atr_ratio",                                # normalised ATR
    "stoch_k",                                  # stochastic momentum
    "dow_sin", "dow_cos",                       # cyclical day-of-week encoding
]
N_MARKET_FEATURES = len(FEATURE_NAMES)   # 16

USER_FEATURE_NAMES = [
    "risk_scaled",
    "cluster_0", "cluster_1", "cluster_2", "cluster_3",  # one-hot
    "horizon_enc",
    "exp_enc",
    "age_scaled",
]
N_USER_FEATURES = len(USER_FEATURE_NAMES)   # 8

STATE_DIM = N_MARKET_FEATURES + N_USER_FEATURES   # 24

# Features already in [0, 1] — skip z-score normalisation
_BOUNDED = {"rsi_14", "bb_pos", "stoch_k", "atr_ratio"}


# ── Raw indicator helpers ────────────────────────────────────────────────────

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    rs = gain / (loss + 1e-10)
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def _macd_histogram(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    macd_line   = _ema(close, fast) - _ema(close, slow)
    signal_line = _ema(macd_line, signal)
    return macd_line - signal_line


def _bollinger_position(close: pd.Series, period: int = 20) -> pd.Series:
    sma   = close.rolling(period).mean()
    std   = close.rolling(period).std()
    upper = sma + 2.0 * std
    lower = sma - 2.0 * std
    return (close - lower) / (upper - lower + 1e-10)


def _stoch_k(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    lowest  = low.rolling(period).min()
    highest = high.rolling(period).max()
    return (close - lowest) / (highest - lowest + 1e-10) * 100.0


# ── Main feature builder ─────────────────────────────────────────────────────

def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Input : OHLCV DataFrame with columns [open, high, low, close, volume].
            May have a DatetimeIndex or a 'timestamp' column.
    Output: DataFrame with columns = FEATURE_NAMES, NaN rows dropped.
            Raw (un-normalised) values suitable for FeatureNormalizer.transform().
    """
    df = df.copy()

    if "timestamp" in df.columns and not isinstance(df.index, pd.DatetimeIndex):
        df = df.set_index("timestamp")
    df.index = pd.to_datetime(df.index)

    close  = df["close"].astype(float)
    high   = df["high"].astype(float)
    low    = df["low"].astype(float)
    volume = df["volume"].astype(float)

    log_close = np.log(close.clip(lower=1e-10))

    feat = pd.DataFrame(index=df.index)

    # ── Returns ──────────────────────────────────────────────────────────────
    feat["log_ret_1"]  = log_close.diff(1)
    feat["log_ret_5"]  = log_close.diff(5)
    feat["log_ret_20"] = log_close.diff(20)

    # ── RSI ──────────────────────────────────────────────────────────────────
    feat["rsi_14"] = (_rsi(close, 14) / 100.0).clip(0.0, 1.0)

    # ── MACD histogram normalised by ATR ─────────────────────────────────────
    atr = _atr(high, low, close, 14)
    feat["macd_hist_norm"] = _macd_histogram(close) / (atr + 1e-10)

    # ── Bollinger Band position ───────────────────────────────────────────────
    feat["bb_pos"] = _bollinger_position(close, 20).clip(0.0, 1.0)

    # ── EMA ratios ────────────────────────────────────────────────────────────
    feat["ema_ratio_short"] = _ema(close, 9)  / (_ema(close, 21) + 1e-10) - 1.0
    feat["ema_ratio_long"]  = _ema(close, 21) / (_ema(close, 50) + 1e-10) - 1.0

    # ── Realised volatility ───────────────────────────────────────────────────
    ret1 = log_close.diff(1)
    feat["vol_10"] = ret1.rolling(10).std()
    feat["vol_20"] = ret1.rolling(20).std()

    # ── Price vs SMA ─────────────────────────────────────────────────────────
    feat["price_vs_sma20"] = close / (close.rolling(20).mean() + 1e-10) - 1.0

    # ── Volume ratio ─────────────────────────────────────────────────────────
    vol_avg = volume.rolling(20).mean()
    feat["volume_ratio"] = (volume / (vol_avg + 1e-10) - 1.0).clip(-1.0, 4.0)

    # ── ATR ratio (normalised to [0, 1]) ─────────────────────────────────────
    feat["atr_ratio"] = (atr / (close + 1e-10)).clip(0.0, 0.1) / 0.1

    # ── Stochastic %K ────────────────────────────────────────────────────────
    feat["stoch_k"] = (_stoch_k(high, low, close, 14) / 100.0).clip(0.0, 1.0)

    # ── Day-of-week cyclical encoding ─────────────────────────────────────────
    dow = df.index.dayofweek.astype(float)
    feat["dow_sin"] = np.sin(2.0 * np.pi * dow / 5.0)
    feat["dow_cos"] = np.cos(2.0 * np.pi * dow / 5.0)

    feat.dropna(inplace=True)
    return feat[FEATURE_NAMES]


def compute_raw_log_returns(df: pd.DataFrame) -> pd.Series:
    """Returns the 1-bar log return series aligned with compute_features() output index."""
    df = df.copy()
    if "timestamp" in df.columns:
        df = df.set_index("timestamp")
    close = df["close"].astype(float)
    return np.log(close.clip(lower=1e-10)).diff(1)


# ── Normaliser ───────────────────────────────────────────────────────────────

class FeatureNormalizer:
    """
    Per-feature clip → z-score normalisation.
    Fit once on training data; reuse identically at inference.
    """

    def __init__(self):
        # Maps feature_name → (clip_lo, clip_hi, mean, std)
        self.stats: dict[str, tuple[float, float, float, float]] = {}

    def fit(self, feat_df: pd.DataFrame) -> "FeatureNormalizer":
        for col in FEATURE_NAMES:
            if col in _BOUNDED:
                self.stats[col] = (0.0, 1.0, 0.0, 1.0)   # pass-through
                continue
            series = feat_df[col].dropna()
            lo  = float(series.quantile(0.01))
            hi  = float(series.quantile(0.99))
            clipped = series.clip(lo, hi)
            mu    = float(clipped.mean())
            sigma = float(clipped.std()) or 1.0
            self.stats[col] = (lo, hi, mu, sigma)
        return self

    def transform(self, feat_df: pd.DataFrame) -> np.ndarray:
        """Returns float32 array of shape (T, N_MARKET_FEATURES)."""
        out = np.zeros((len(feat_df), N_MARKET_FEATURES), dtype=np.float32)
        for i, col in enumerate(FEATURE_NAMES):
            lo, hi, mu, sigma = self.stats[col]
            vals = feat_df[col].values.astype(float)
            vals = np.clip(vals, lo, hi)
            if col not in _BOUNDED:
                vals = (vals - mu) / sigma
            out[:, i] = vals
        return out

    def fit_transform(self, feat_df: pd.DataFrame) -> np.ndarray:
        self.fit(feat_df)
        return self.transform(feat_df)

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self.stats, f)

    @classmethod
    def load(cls, path: str) -> "FeatureNormalizer":
        norm = cls()
        with open(path, "rb") as f:
            norm.stats = pickle.load(f)
        return norm


# ── User profile encoder ──────────────────────────────────────────────────────

_HORIZON_MAP: dict[str, float] = {
    "1 Year": 0.0,  "1 year": 0.0,
    "3-5 Years": 0.33, "3-5 years": 0.33,
    "5-10 Years": 0.67, "5-10 years": 0.67,
    "10+ Years": 1.0, "10+ years": 1.0,
}
_EXPERIENCE_MAP: dict[str, float] = {
    "Beginner": 0.0,     "beginner": 0.0,
    "Intermediate": 0.5, "intermediate": 0.5,
    "Advanced": 1.0,     "advanced": 1.0,
}


def encode_user_profile(profile: dict) -> np.ndarray:
    """
    Converts a user MongoDB document (or any dict with the same keys) into
    the 8-dimensional user feature vector used by the PPO agent.
    Missing fields fall back to sensible mid-range defaults.
    """
    risk = float(profile.get("risk_tolerance", 5)) / 10.0

    cluster = int(profile["cluster"]) if profile.get("cluster") is not None else 1
    cluster = max(0, min(3, cluster))
    one_hot = np.zeros(4, dtype=np.float32)
    one_hot[cluster] = 1.0

    horiz = _HORIZON_MAP.get(str(profile.get("investment_horizon", "3-5 Years")), 0.33)
    exp   = _EXPERIENCE_MAP.get(str(profile.get("experience", "Beginner")), 0.0)
    age   = float(profile.get("age", 35)) / 100.0

    return np.array([risk, *one_hot, horiz, exp, age], dtype=np.float32)  # (8,)
