import pandas as pd
import numpy as np

TRADING_DAYS = 252


def calculate_annualized_return(price_history: pd.DataFrame) -> float:
    """Annualized cumulative return per paper formula:
    R_annualized = (1 + R_cumulative)^(252/n) - 1
    """
    prices = price_history["Close"].dropna()
    if len(prices) < 2:
        return 0.0
    r_cum = (prices.iloc[-1] / prices.iloc[0]) - 1
    n = len(prices)
    return float((1 + r_cum) ** (TRADING_DAYS / n) - 1)


def calculate_annualized_volatility(price_history: pd.DataFrame) -> float:
    """Annualized volatility per paper formula:
    sigma_annualized = sigma_daily * sqrt(252)
    """
    prices = price_history["Close"].dropna()
    if len(prices) < 2:
        return 0.0
    daily_returns = prices.pct_change().dropna()
    return float(daily_returns.std() * np.sqrt(TRADING_DAYS))


def calculate_price_metrics(price_history: pd.DataFrame) -> dict:
    """Return a dict of key price metrics for the valuation agent."""
    if price_history.empty:
        return {}

    prices = price_history["Close"].dropna()
    volumes = price_history["Volume"].dropna()

    ann_return = calculate_annualized_return(price_history)
    ann_vol = calculate_annualized_volatility(price_history)

    return {
        "current_price": round(float(prices.iloc[-1]), 2),
        "start_price": round(float(prices.iloc[0]), 2),
        "period_return_pct": round(((prices.iloc[-1] / prices.iloc[0]) - 1) * 100, 2),
        "annualized_return": round(ann_return, 4),
        "annualized_volatility": round(ann_vol, 4),
        "avg_daily_volume": round(float(volumes.mean()), 0),
        "price_high": round(float(prices.max()), 2),
        "price_low": round(float(prices.min()), 2),
        "num_trading_days": len(prices),
    }


def format_metrics_for_llm(metrics: dict, ticker_str: str) -> str:
    """Format price metrics into readable text for the valuation agent."""
    if not metrics:
        return "Price and volume data not available."

    return f"""## Price & Valuation Metrics  ({ticker_str}, 3-month window)

Current Price:        {metrics.get('current_price', 'N/A'):>12} KRW
Period Start Price:   {metrics.get('start_price', 'N/A'):>12} KRW
Period Return:        {metrics.get('period_return_pct', 'N/A'):>11}%
Annualized Return:    {metrics.get('annualized_return', 0) * 100:>10.2f}%
Annualized Volatility:{metrics.get('annualized_volatility', 0) * 100:>10.2f}%
Avg Daily Volume:     {metrics.get('avg_daily_volume', 0):>12,.0f} shares
3M High:              {metrics.get('price_high', 'N/A'):>12} KRW
3M Low:               {metrics.get('price_low', 'N/A'):>12} KRW
Trading Days:         {metrics.get('num_trading_days', 'N/A'):>12}
"""
