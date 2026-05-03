import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


def get_yfinance_ticker(stock_code: str) -> tuple:
    """Auto-detect KOSPI (.KS) or KOSDAQ (.KQ) and return (Ticker, ticker_str)."""
    for suffix in [".KS", ".KQ"]:
        ticker_str = f"{stock_code}{suffix}"
        t = yf.Ticker(ticker_str)
        hist = t.history(period="5d")
        if not hist.empty:
            return t, ticker_str
    raise ValueError(
        f"Could not find yfinance data for stock code '{stock_code}'. "
        "Tried .KS (KOSPI) and .KQ (KOSDAQ)."
    )


def fetch_price_history(ticker: yf.Ticker, as_of_date: datetime, months: int = 3) -> pd.DataFrame:
    """Fetch OHLCV price history for `months` months ending on as_of_date."""
    start = as_of_date - timedelta(days=30 * months)
    end   = as_of_date + timedelta(days=1)   # yfinance end is exclusive
    return ticker.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))


def fetch_news(ticker: yf.Ticker, as_of_date: datetime,
               max_items: int = 10, months: int = 3) -> list:
    """Fetch news articles published within `months` months before as_of_date."""
    try:
        news = ticker.news or []
        cutoff_ts  = (as_of_date - timedelta(days=30 * months)).timestamp()
        as_of_ts   = as_of_date.timestamp()
        filtered = [
            item for item in news
            if cutoff_ts <= item.get("providerPublishTime", 0) <= as_of_ts
        ]
        return filtered[:max_items]
    except Exception:
        return []


def format_news_for_llm(news_items: list) -> str:
    """Format news list into readable text for the sentiment agent."""
    if not news_items:
        return "No recent news available for this stock."

    lines = []
    for i, item in enumerate(news_items, 1):
        title = item.get("title", "No title")
        publisher = item.get("publisher", "Unknown")
        summary = item.get("summary") or item.get("description") or ""
        pub_ts = item.get("providerPublishTime", 0)
        date_str = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d") if pub_ts else "Unknown date"

        lines.append(f"{i}. [{date_str}] {title}  (Source: {publisher})")
        if summary:
            lines.append(f"   {summary[:300]}")
        lines.append("")

    return "\n".join(lines)
