from datetime import datetime
from typing import Optional

import pandas as pd
import yfinance as yf

from backtest.engine import BacktestEngine, MetricsCalculator

_RISK_FREE_RATE  = 0.035   # ~KRX CD rate
_ROLLING_WINDOW  = 30


def _fetch_sp500(start: str, end: str) -> tuple[Optional[pd.Series], Optional[pd.Series]]:
    """
    Fetch S&P 500 daily returns and compute:
      - cumulative return series
      - rolling Sharpe series (30-day window)

    Returns (None, None) on any failure so callers can safely skip.
    """
    try:
        hist = yf.Ticker("^GSPC").history(start=start, end=end)
        if hist.empty:
            return None, None
        returns = hist["Close"].pct_change().dropna()
        mc      = MetricsCalculator(risk_free_rate=_RISK_FREE_RATE)
        return mc.cumulative_return(returns), mc.rolling_sharpe(returns, _ROLLING_WINDOW)
    except Exception as e:
        print(f"[WARNING] Could not fetch S&P 500: {e}")
        return None, None


def run_backtest(
    portfolios: dict,
    as_of_date: datetime,
    end_date: datetime,
    company_name: str,
    stock_code: str,
    all_stock_codes: Optional[list] = None,
) -> dict:
    """
    Run a separate BacktestEngine per risk profile, with two benchmarks:
      1. Equal-weight (EW) — all analyzed stocks, regardless of signal
      2. S&P 500            — fetched via yfinance, overlaid on the plot

    Plotting is NOT done here — the orchestrator calls plot_two_profiles()
    directly so it can embed the figure into the PDF.

    Parameters
    ----------
    portfolios      : {"risk-averse": portfolio_dict, "risk-neutral": portfolio_dict}
    as_of_date      : backtest start date (= analysis as_of_date)
    end_date        : backtest end date (user-supplied)
    company_name    : used in console output
    stock_code      : used in console output
    all_stock_codes : full list of analyzed stock codes for EW benchmark

    Returns
    -------
    {
        "risk-averse":    BacktestEngine,
        "risk-neutral":   BacktestEngine,
        "summaries":      dict,
        "sp500_cum":      pd.Series | None,
        "sp500_rolling":  pd.Series | None,
    }
    """
    start_str = as_of_date.strftime("%Y-%m-%d")
    end_str   = end_date.strftime("%Y-%m-%d")

    engines   = {}
    summaries = {}

    # Equal-weight benchmark weights (all analyzed stocks, no bond)
    ew_weights = None
    if all_stock_codes and len(all_stock_codes) > 0:
        w          = 1.0 / len(all_stock_codes)
        ew_weights = {code: w for code in all_stock_codes}

    for profile in ["risk-averse", "risk-neutral"]:
        engine = BacktestEngine(
            start_date=start_str,
            end_date=end_str,
            risk_free_rate=_RISK_FREE_RATE,
            rolling_window=_ROLLING_WINDOW,
            market="KRX",
        )
        # Agent portfolio
        engine.add_portfolio(
            name=profile.title(),
            signals={},
            custom_weights=portfolios[profile]["weights"],
        )
        # EW benchmark (all stocks, equal weight)
        if ew_weights:
            engine.add_portfolio(
                name="EW Benchmark",
                signals={},
                custom_weights=ew_weights,
            )

        profile_summaries  = engine.run()
        engines[profile]   = engine
        summaries[profile] = profile_summaries
        engine.print_summary()

    # S&P 500 benchmark series
    sp500_cum, sp500_rolling = _fetch_sp500(start_str, end_str)
    if sp500_cum is not None:
        print("  [S&P 500] Benchmark fetched successfully.")
    else:
        print("  [S&P 500] Benchmark unavailable — will be omitted from chart.")

    return {
        "risk-averse":   engines["risk-averse"],
        "risk-neutral":  engines["risk-neutral"],
        "summaries":     summaries,
        "sp500_cum":     sp500_cum,
        "sp500_rolling": sp500_rolling,
    }
