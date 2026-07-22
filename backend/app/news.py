"""News & sentiment data layer — mirrors modules/news_fetcher.py and
modules/ai/sentiment.py function-for-function so headlines and FinBERT
scores stay identical to the Streamlit app.
"""
import datetime
import html as _html_mod
import os
import re
import time
from email.utils import parsedate_to_datetime
from functools import lru_cache

import requests

_ALPACA_NEWS_URL = "https://data.alpaca.markets/v1beta1/news"
_GNEWS_BASE = "https://news.google.com/rss/search"
CACHE_TTL_SECONDS = 900

_cache: dict[str, tuple[float, object]] = {}


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, value = entry
    if time.time() - ts > CACHE_TTL_SECONDS:
        return None
    return value


def _cache_set(key: str, value):
    _cache[key] = (time.time(), value)


def _alpaca_headers() -> dict | None:
    key = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        return None
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret, "accept": "application/json"}


def _parse_articles(raw: list) -> list[dict]:
    articles = []
    for a in raw:
        images = a.get("images") or []
        image_url = images[0].get("url", "") if images else ""
        articles.append({
            "id": a.get("id"),
            "headline": a.get("headline", ""),
            "summary": a.get("summary", ""),
            "author": a.get("author", ""),
            "source": a.get("source", ""),
            "url": a.get("url", ""),
            "published_at": a.get("created_at", ""),
            "symbols": a.get("symbols", []),
            "image_url": image_url,
        })
    return articles


def get_market_news(limit: int = 20) -> list[dict]:
    cache_key = f"market_news:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    headers = _alpaca_headers()
    if headers is None:
        return []
    params = {"limit": min(limit, 50), "sort": "desc", "include_content": "false"}
    try:
        resp = requests.get(_ALPACA_NEWS_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        result = _parse_articles(resp.json().get("news", []))
        _cache_set(cache_key, result)
        return result
    except Exception:
        return []


def get_ticker_news(ticker: str, limit: int = 15) -> list[dict]:
    cache_key = f"ticker_news:{ticker}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    headers = _alpaca_headers()
    if headers is None:
        return []
    params = {"symbols": ticker.upper().strip(), "limit": min(limit, 50), "sort": "desc", "include_content": "false"}
    try:
        resp = requests.get(_ALPACA_NEWS_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        result = _parse_articles(resp.json().get("news", []))
        _cache_set(cache_key, result)
        return result
    except Exception:
        return []


def _parse_gnews_feed(feed_url: str, limit: int) -> list[dict]:
    try:
        import feedparser
    except ImportError:
        return []
    try:
        feed = feedparser.parse(feed_url)
    except Exception:
        return []

    articles = []
    for entry in feed.entries[:limit]:
        published_at = ""
        try:
            published_at = parsedate_to_datetime(entry.get("published", "")).isoformat()
        except Exception:
            published_at = entry.get("published", "")

        headline_text = entry.get("title", "")
        raw_summary = re.sub(r"<[^>]+>", " ", entry.get("summary", ""))
        raw_summary = _html_mod.unescape(raw_summary)
        raw_summary = re.sub(r"\s+", " ", raw_summary).strip()
        if raw_summary.lower().startswith(headline_text[:50].lower()):
            raw_summary = ""

        source = ""
        try:
            source = entry.source.title
        except AttributeError:
            pass

        articles.append({
            "id": entry.get("id", ""),
            "headline": entry.get("title", ""),
            "summary": raw_summary,
            "author": "",
            "source": source,
            "url": entry.get("link", ""),
            "published_at": published_at,
            "symbols": [],
            "image_url": "",
        })
    return articles


def get_psx_market_news(limit: int = 20) -> list[dict]:
    cache_key = f"psx_market_news:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    url = f"{_GNEWS_BASE}?q=Pakistan+Stock+Exchange+KSE-100&hl=en&gl=PK&ceid=PK:en"
    result = _parse_gnews_feed(url, limit)
    _cache_set(cache_key, result)
    return result


def get_psx_company_news(company_name: str, limit: int = 15) -> list[dict]:
    cache_key = f"psx_company_news:{company_name}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    query = company_name.strip().replace(" ", "+") + "+Pakistan+stock"
    url = f"{_GNEWS_BASE}?q={query}&hl=en&gl=PK&ceid=PK:en"
    result = _parse_gnews_feed(url, limit)
    _cache_set(cache_key, result)
    return result


# ==============================================================================
# SENTIMENT (FinBERT)
# ==============================================================================

_CONFIDENCE_THRESHOLD = 0.60

_IMPACT = {
    "positive": ("Likely Positive Market Impact", "#22C55E"),
    "negative": ("Likely Negative Market Impact", "#EF4444"),
    "neutral": ("Neutral / No Clear Market Impact", "#A1A1AA"),
}

_LABELS = ["positive", "negative", "neutral"]


@lru_cache(maxsize=1)
def _load_finbert():
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
    model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
    model.eval()
    return tokenizer, model


def _inconclusive(probs: dict | None = None) -> dict:
    return {
        "label": "neutral",
        "confidence": 0.0,
        "probabilities": probs or {"positive": 0.33, "negative": 0.33, "neutral": 0.34},
        "impact_label": "Inconclusive",
        "impact_color": "#64748b",
        "inconclusive": True,
    }


def analyze_sentiment(text: str) -> dict:
    if not text or not text.strip():
        return _inconclusive()
    try:
        import torch
        import torch.nn.functional as F

        tokenizer, model = _load_finbert()
        inputs = tokenizer(text[:1000], return_tensors="pt", truncation=True, max_length=512, padding=True)
        with torch.no_grad():
            logits = model(**inputs).logits
        probs = F.softmax(logits, dim=-1)[0]
        prob_dict = {_LABELS[i]: probs[i].item() for i in range(len(_LABELS))}
        best_idx = int(probs.argmax())
        label = _LABELS[best_idx]
        confidence = probs[best_idx].item()
        if confidence < _CONFIDENCE_THRESHOLD:
            return _inconclusive(prob_dict)
        impact_label, impact_color = _IMPACT.get(label, ("Neutral", "#A1A1AA"))
        return {
            "label": label,
            "confidence": confidence,
            "probabilities": prob_dict,
            "impact_label": impact_label,
            "impact_color": impact_color,
            "inconclusive": False,
        }
    except Exception:
        return _inconclusive()


def analyze_articles(articles: list[dict]) -> list[dict]:
    enriched = []
    for article in articles:
        text = article.get("headline", "") + ". " + article.get("summary", "")
        enriched.append({**article, "sentiment": analyze_sentiment(text)})
    return enriched


def enriched_market_news(limit: int = 20) -> list[dict]:
    cache_key = f"enriched_market:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    result = analyze_articles(get_market_news(limit))
    _cache_set(cache_key, result)
    return result


def enriched_ticker_news(ticker: str, limit: int = 15) -> list[dict]:
    cache_key = f"enriched_ticker:{ticker}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    result = analyze_articles(get_ticker_news(ticker, limit))
    _cache_set(cache_key, result)
    return result


def enriched_psx_market_news(limit: int = 20) -> list[dict]:
    cache_key = f"enriched_psx_market:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    result = analyze_articles(get_psx_market_news(limit))
    _cache_set(cache_key, result)
    return result


def enriched_psx_company_news(company_name: str, limit: int = 15) -> list[dict]:
    cache_key = f"enriched_psx_company:{company_name}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    result = analyze_articles(get_psx_company_news(company_name, limit))
    _cache_set(cache_key, result)
    return result


PSX_STOCKS = {
    "HBL": "Habib Bank Limited", "ENGRO": "Engro Corporation", "LUCK": "Lucky Cement",
    "MCB": "MCB Bank", "UBL": "United Bank Limited", "PPL": "Pakistan Petroleum",
    "OGDC": "Oil & Gas Dev. Company", "PSO": "Pakistan State Oil", "NESTLE": "Nestle Pakistan",
    "SYS": "Systems Limited", "TRG": "TRG Pakistan", "HUBC": "Hub Power Company",
    "ATRL": "Attock Refinery", "MEBL": "Meezan Bank", "NBP": "National Bank of Pakistan",
    "FFC": "Fauji Fertilizer Company", "EFERT": "Engro Fertilizers", "DGKC": "D.G. Khan Cement",
    "COLG": "Colgate-Palmolive Pakistan", "GLAXO": "GlaxoSmithKline Pakistan",
}
