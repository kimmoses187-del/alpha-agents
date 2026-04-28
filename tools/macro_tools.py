import yfinance as yf

# Key macro indicators fetchable via yfinance
MACRO_TICKERS: dict = {
    "USD/KRW":         "KRW=X",
    "KOSPI":           "^KS11",
    "KOSDAQ":          "^KQ11",
    "S&P 500":         "^GSPC",
    "NASDAQ":          "^IXIC",
    "US 10Y Treasury": "^TNX",
    "Gold (USD)":      "GC=F",
    "Crude Oil (WTI)": "CL=F",
}


def fetch_macro_indicators(period: str = "3mo") -> dict:
    """Fetch current value and 3-month return for each macro indicator."""
    results = {}
    for name, sym in MACRO_TICKERS.items():
        try:
            hist = yf.Ticker(sym).history(period=period)
            if hist.empty:
                continue
            current = float(hist["Close"].iloc[-1])
            start   = float(hist["Close"].iloc[0])
            ret     = round((current / start - 1) * 100, 2)
            results[name] = {
                "current":   round(current, 4),
                "3m_return": ret,
                "direction": "▲" if ret >= 0 else "▼",
            }
        except Exception:
            continue
    return results


def format_macro_data_for_llm(macro_data: dict, sector: str) -> str:
    lines = []

    lines += [
        "## Macroeconomic Indicators (3-Month Window)",
        "",
        f"{'Indicator':<25} {'Current':>14} {'3M Change':>12}",
        "-" * 54,
    ]

    for name, data in macro_data.items():
        direction = data.get("direction", "")
        current   = data.get("current", "N/A")
        ret       = data.get("3m_return", "N/A")
        lines.append(f"{name:<25} {str(current):>14} {direction} {ret}%")

    lines += [
        "",
        "## Key Macro Signals for Korean Equities",
        "",
        "USD/KRW: A rising KRW=X (weakening KRW) benefits Korean exporters but raises "
        "import costs. A falling USD/KRW (strengthening KRW) pressures export revenues.",
        "",
        "US 10Y Treasury: Higher US yields attract capital away from emerging markets "
        "including Korea, typically pressuring equity valuations.",
        "",
        "KOSPI vs S&P 500: Divergence between KOSPI and US indices often signals "
        "Korea-specific risk or opportunity beyond global trends.",
        "",
        f"## Sector Under Analysis: {sector}",
        "Consider how the above macro conditions specifically affect this sector's "
        "demand outlook, cost structure, and capital flows.",
    ]

    return "\n".join(lines)
