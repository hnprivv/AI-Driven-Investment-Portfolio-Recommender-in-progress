from fastapi import APIRouter

from app import news as news_module

router = APIRouter()


@router.get("/market")
def get_market_news(limit: int = 20):
    articles = news_module.enriched_market_news(limit)
    return {"articles": articles}


@router.get("/ticker")
def get_ticker_news(symbol: str, limit: int = 15):
    articles = news_module.enriched_ticker_news(symbol.upper().strip(), limit)
    return {"articles": articles}


@router.get("/psx/market")
def get_psx_market_news(limit: int = 20):
    articles = news_module.enriched_psx_market_news(limit)
    return {"articles": articles}


@router.get("/psx/company")
def get_psx_company_news(query: str, limit: int = 15):
    query_upper = query.upper().strip()
    if query_upper in news_module.PSX_STOCKS:
        company_name = news_module.PSX_STOCKS[query_upper]
        display_label = f"{query_upper} — {company_name}"
    else:
        company_name = query.strip()
        display_label = query.strip()

    articles = news_module.enriched_psx_company_news(company_name, limit)
    return {"articles": articles, "display_label": display_label}
