import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from tools.dart_tools import lookup_company, fetch_financial_statements, format_financial_data
from tools.yfinance_tools import get_yfinance_ticker, fetch_price_history, fetch_news, format_news_for_llm
from tools.metrics_tools import calculate_price_metrics, format_metrics_for_llm
from tools.market_tools import get_company_sector_info, get_kospi_return, get_peer_comparison, format_market_data_for_llm
from tools.macro_tools import fetch_macro_indicators, format_macro_data_for_llm
from debate.debate_manager import DebateManager
from report.report_generator import generate_report

REPORTS_DIR = "reports"
PROFILES = ("risk-averse", "risk-neutral")


def _run_profile(profile: str, company_name: str, corp_info: dict,
                 fundamental_data: str, sentiment_data: str,
                 valuation_data: str, market_data: str, macro_data: str,
                 metrics: dict, ticker_str: str, stock_code: str) -> dict:
    """Run the full debate + report pipeline for one risk profile."""
    print(f"\n  [{profile.upper()}] Starting multi-agent debate...")

    manager = DebateManager(risk_profile=profile)
    debate_result = manager.run(
        company_name=company_name,
        fundamental_data=fundamental_data,
        sentiment_data=sentiment_data,
        valuation_data=valuation_data,
        market_data=market_data,
        macro_data=macro_data,
    )

    report_md = generate_report(debate_result, corp_info, metrics, ticker_str, profile)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    profile_tag = "neutral" if profile == "risk-neutral" else "averse"
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M")
    filename    = os.path.join(REPORTS_DIR, f"{stock_code}_{profile_tag}_{timestamp}.md")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report_md)

    return {
        "profile":        profile,
        "signal":         debate_result["final_signal"],
        "consensus_type": debate_result["consensus_type"],
        "rounds":         debate_result["consensus_round"],
        "filename":       filename,
    }


def run(stock_code: str) -> None:
    print(f"\n{'='*60}")
    print(f" AlphaAgents — Korean Equity Analysis")
    print(f" Stock Code  : {stock_code}")
    print(f" Profiles    : Risk-Averse  |  Risk-Neutral")
    print(f"{'='*60}")

    # ── Step 1: DART company lookup ───────────────────────────────────────
    print("\n[1/3] Looking up company on OpenDART...")
    corp_info    = lookup_company(stock_code)
    corp_code    = corp_info["corp_code"]
    company_name = corp_info["corp_name"]
    print(f"  Found: {company_name}  (corp_code: {corp_code})")

    # ── Step 2: Fetch all data (once, shared by both profiles) ───────────
    print("\n[2/3] Fetching data...")

    current_year = datetime.now().year - 1
    print(f"  DART: fetching financials for FY{current_year} and FY{current_year - 1}...")
    fs_current = fetch_financial_statements(corp_code, current_year)
    fs_prev    = fetch_financial_statements(corp_code, current_year - 1)
    fundamental_data = format_financial_data(corp_info, fs_current, fs_prev)

    print("  yfinance: detecting exchange and fetching price history + news...")
    ticker_obj, ticker_str = get_yfinance_ticker(stock_code)
    price_history  = fetch_price_history(ticker_obj, period="3mo")
    news_items     = fetch_news(ticker_obj)
    metrics        = calculate_price_metrics(price_history)
    sentiment_data = format_news_for_llm(news_items)
    valuation_data = format_metrics_for_llm(metrics, ticker_str)

    # Market & industry data
    print("  Fetching sector/industry and peer comparison data...")
    sector_info  = get_company_sector_info(ticker_obj)
    kospi_return = get_kospi_return()
    peers        = get_peer_comparison(ticker_str, sector_info.get("sector", ""))
    market_data  = format_market_data_for_llm(sector_info, kospi_return, peers, company_name)

    # Macro data
    print("  Fetching macroeconomic indicators...")
    macro_indicators = fetch_macro_indicators()
    macro_data       = format_macro_data_for_llm(macro_indicators, sector_info.get("sector", "Unknown"))

    print(f"  Exchange: {ticker_str} | "
          f"{len(price_history)} trading days | "
          f"{len(news_items)} news items | "
          f"{len(peers)} peers | "
          f"{len(macro_indicators)} macro indicators")

    # ── Step 3: Both profiles in parallel ────────────────────────────────
    print(f"\n[3/3] Running both risk profiles in parallel...")

    shared_kwargs = dict(
        company_name=company_name,
        corp_info=corp_info,
        fundamental_data=fundamental_data,
        sentiment_data=sentiment_data,
        valuation_data=valuation_data,
        market_data=market_data,
        macro_data=macro_data,
        metrics=metrics,
        ticker_str=ticker_str,
        stock_code=stock_code,
    )

    results = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(_run_profile, profile, **shared_kwargs): profile
            for profile in PROFILES
        }
        for future in as_completed(futures):
            profile = futures[future]
            try:
                results[profile] = future.result()
            except Exception as exc:
                print(f"  [{profile}] FAILED: {exc}")
                results[profile] = {"profile": profile, "signal": "ERROR", "error": str(exc)}

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f" RESULTS — {company_name} ({stock_code})")
    print(f"{'='*60}")
    for profile in PROFILES:
        r = results.get(profile, {})
        if r.get("signal") == "ERROR":
            print(f" {profile.title():<14}: ERROR — {r.get('error')}")
        else:
            print(f" {profile.title():<14}: {r['signal']:<4}  "
                  f"({r['consensus_type'].title()}, {r['rounds']} round(s))")
            print(f"   Report: {r['filename']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  AlphaAgents — Korean Equity Analysis")
    print("="*60)
    stock_code = input("\n  Enter stock ticker (e.g. 005930): ").strip()
    if not stock_code:
        print("  No ticker entered. Exiting.")
        sys.exit(1)
    run(stock_code)
