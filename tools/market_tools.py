import yfinance as yf
from datetime import datetime, timedelta

# Sector → representative Korean peer tickers (KOSPI .KS)
# Used to fetch peer comparison data for the Market Agent
KOREAN_SECTOR_PEERS: dict = {
    "Technology": ["005930.KS", "000660.KS", "035420.KS", "066570.KS"],
    "Communication Services": ["030200.KS", "017670.KS", "036570.KS"],
    "Consumer Cyclical": ["005380.KS", "000270.KS", "012330.KS", "032640.KS"],
    "Consumer Defensive": ["097950.KS", "003230.KS", "004370.KS"],
    "Healthcare": ["068270.KS", "207940.KS", "326030.KS", "128940.KS"],
    "Financial Services": ["105560.KS", "055550.KS", "086790.KS", "138930.KS"],
    "Basic Materials": ["003670.KS", "010130.KS", "011070.KS"],
    "Energy": ["096770.KS", "267250.KS"],
    "Industrials": ["042660.KS", "329180.KS", "010140.KS", "047810.KS"],
    "Real Estate": ["016380.KS"],
}


def get_company_sector_info(ticker_obj: yf.Ticker) -> dict:
    """Pull sector, industry, and key ratio data from yfinance .info."""
    info = ticker_obj.info
    return {
        "sector":             info.get("sector", "Unknown"),
        "industry":           info.get("industry", "Unknown"),
        "description":        info.get("longBusinessSummary", ""),
        "market_cap":         info.get("marketCap"),
        "pe_ratio":           info.get("trailingPE"),
        "forward_pe":         info.get("forwardPE"),
        "pb_ratio":           info.get("priceToBook"),
        "revenue_growth":     info.get("revenueGrowth"),
        "earnings_growth":    info.get("earningsGrowth"),
        "gross_margins":      info.get("grossMargins"),
        "operating_margins":  info.get("operatingMargins"),
        "full_time_employees": info.get("fullTimeEmployees"),
    }


def _date_range(as_of_date: datetime, months: int = 3) -> tuple[str, str]:
    """Return (start_str, end_str) for a `months`-month window ending on as_of_date."""
    start = as_of_date - timedelta(days=30 * months)
    end   = as_of_date + timedelta(days=1)   # yfinance end is exclusive
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def get_kospi_return(as_of_date: datetime, months: int = 3) -> float | None:
    """Return KOSPI index return for `months` months ending on as_of_date."""
    try:
        start, end = _date_range(as_of_date, months)
        hist = yf.Ticker("^KS11").history(start=start, end=end)
        if not hist.empty:
            return round((hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100, 2)
    except Exception:
        pass
    return None


def get_peer_comparison(ticker_str: str, sector: str,
                        as_of_date: datetime, months: int = 3) -> list:
    """Fetch basic return and valuation for up to 3 sector peers ending on as_of_date."""
    start, end = _date_range(as_of_date, months)
    candidates = [t for t in KOREAN_SECTOR_PEERS.get(sector, []) if t != ticker_str]
    peers = []
    for pt in candidates[:3]:
        try:
            t    = yf.Ticker(pt)
            info = t.info
            hist = t.history(start=start, end=end)
            ret  = None
            if not hist.empty:
                ret = round((hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100, 2)
            name = info.get("shortName") or info.get("longName") or pt
            peers.append({
                "ticker":     pt,
                "name":       name,
                "3m_return":  ret,
                "pe_ratio":   info.get("trailingPE"),
                "pb_ratio":   info.get("priceToBook"),
                "market_cap": info.get("marketCap"),
            })
        except Exception:
            continue
    return peers


def format_market_data_for_llm(sector_info: dict, kospi_return: float | None,
                                peers: list, company_name: str) -> str:
    lines = []

    # Sector classification & ratios
    lines += [
        "## Sector & Industry Classification",
        f"Sector:              {sector_info.get('sector', 'N/A')}",
        f"Industry:            {sector_info.get('industry', 'N/A')}",
        f"Full-time Employees: {sector_info.get('full_time_employees', 'N/A')}",
        f"Market Cap:          {sector_info.get('market_cap', 'N/A')}",
        "",
        "## Key Valuation Ratios",
        f"Trailing P/E:        {sector_info.get('pe_ratio', 'N/A')}",
        f"Forward P/E:         {sector_info.get('forward_pe', 'N/A')}",
        f"Price/Book:          {sector_info.get('pb_ratio', 'N/A')}",
        f"Revenue Growth (YoY):{sector_info.get('revenue_growth', 'N/A')}",
        f"Earnings Growth:     {sector_info.get('earnings_growth', 'N/A')}",
        f"Gross Margin:        {sector_info.get('gross_margins', 'N/A')}",
        f"Operating Margin:    {sector_info.get('operating_margins', 'N/A')}",
        "",
    ]

    # Business description
    desc = sector_info.get("description", "")
    if desc:
        lines += ["## Business Description", desc[:600], ""]

    # Sector vs KOSPI
    lines += [
        "## Benchmark Comparison (3-Month)",
        f"KOSPI 3M Return: {kospi_return}%" if kospi_return is not None else "KOSPI: N/A",
        "",
    ]

    # Peer comparison table
    if peers:
        lines += ["## Sector Peer Comparison (3-Month)", ""]
        lines.append(f"{'Company':<35} {'3M Return':>12} {'P/E':>8} {'P/B':>8}")
        lines.append("-" * 68)
        for p in peers:
            ret_str = f"{p['3m_return']}%" if p["3m_return"] is not None else "N/A"
            pe_str  = f"{p['pe_ratio']:.1f}" if p["pe_ratio"] else "N/A"
            pb_str  = f"{p['pb_ratio']:.2f}" if p["pb_ratio"] else "N/A"
            lines.append(f"{p['name']:<35} {ret_str:>12} {pe_str:>8} {pb_str:>8}")
        lines.append("")

    return "\n".join(lines)
