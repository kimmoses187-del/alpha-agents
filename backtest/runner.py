from datetime import datetime
from typing import Optional

import pandas as pd
import yfinance as yf

from backtest.engine import BacktestEngine, MetricsCalculator

_RISK_FREE_RATE  = 0.035   # ~KRX CD rate
_ROLLING_WINDOW  = 30


def _fetch_index(ticker: str, label: str,
                 start: str, end: str
                 ) -> tuple[Optional[pd.Series], Optional[pd.Series]]:
    """
    Fetch a yfinance index and compute:
      - cumulative return series
      - rolling Sharpe series (30-day window)

    Returns (None, None) on any failure so callers can safely skip.
    """
    try:
        hist = yf.Ticker(ticker).history(start=start, end=end)
        if hist.empty:
            return None, None
        returns = hist["Close"].pct_change().dropna()
        mc      = MetricsCalculator(risk_free_rate=_RISK_FREE_RATE)
        return mc.cumulative_return(returns), mc.rolling_sharpe(returns, _ROLLING_WINDOW)
    except Exception as e:
        print(f"[WARNING] Could not fetch {label}: {e}")
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
    Run a separate BacktestEngine per risk profile, with three benchmarks:
      1. Equal-weight (EW) — all analyzed stocks, regardless of signal
      2. KOSPI              — ^KS11 via yfinance, overlaid on the plot
      3. KOSDAQ             — ^KQ11 via yfinance, overlaid on the plot

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
        "kospi_cum":      pd.Series | None,
        "kospi_rolling":  pd.Series | None,
        "kosdaq_cum":     pd.Series | None,
        "kosdaq_rolling": pd.Series | None,
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

    # Korean index benchmarks
    kospi_cum,  kospi_rolling  = _fetch_index("^KS11", "KOSPI",  start_str, end_str)
    kosdaq_cum, kosdaq_rolling = _fetch_index("^KQ11", "KOSDAQ", start_str, end_str)

    for label, series in [("KOSPI", kospi_cum), ("KOSDAQ", kosdaq_cum)]:
        if series is not None:
            print(f"  [{label}] Benchmark fetched successfully.")
        else:
            print(f"  [{label}] Benchmark unavailable — will be omitted from chart.")

    return {
        "risk-averse":    engines["risk-averse"],
        "risk-neutral":   engines["risk-neutral"],
        "summaries":      summaries,
        "kospi_cum":      kospi_cum,
        "kospi_rolling":  kospi_rolling,
        "kosdaq_cum":     kosdaq_cum,
        "kosdaq_rolling": kosdaq_rolling,
    }
