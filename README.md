# AlphaAgents 🤖📈
### LLM Multi-Agent System for Korean Equity Research

A partial replication of **BlackRock's AlphaAgents** (Zhao et al., 2025) adapted for Korean equities (KOSPI/KOSDAQ).  
**Five specialized AI agents** collaborate, debate, and reach a consensus **BUY / SELL** recommendation — simultaneously under both **Risk-Averse** and **Risk-Neutral** investor profiles.

---

## Overview

Traditional equity research requires analysts to process vast amounts of financial disclosures, market news, price data, industry reports, and macroeconomic signals simultaneously. This system automates that process using a team of five LLM-powered agents, each specialising in a distinct analytical lens — mirroring how a real investment committee operates.

```
python3 main.py
        │
        ▼
  Enter stock ticker
        │
        ▼
┌───────────────────────────────────────────────────────┐
│                  Data Fetching  (shared)               │
│                                                        │
│  OpenDART          yfinance          yfinance          │
│  사업보고서          Price / News       Sector / Macro   │
│  분기보고서          (3-month OHLCV)    KRW/USD · KOSPI  │
└──────────────────────────┬────────────────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
       [Risk-Averse]               [Risk-Neutral]       ← parallel
             │                           │
             ▼                           ▼
┌────────────────────────────────────────────────────┐
│                 5 Specialist Agents                  │
│                                                      │
│  Fundamental  │  Sentiment  │  Valuation  │          │
│  Market       │  Macro                              │
└──────────────────────────┬─────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│                  Debate Mechanism                     │
│                                                      │
│  Round 0   — Independent analysis → check unanimous  │
│  Round 1–3 — Each agent reads all peers → update     │
│              position → check unanimous              │
│  After R3  — Majority vote (3-of-5)                  │
│              No tie possible with 5 binary agents    │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
              Markdown Report × 2
         (risk-averse  +  risk-neutral)
```

---

## The Five Agents

| Agent | Data Source | Analytical Lens |
|---|---|---|
| **Fundamental** | OpenDART (사업보고서 / 분기보고서) | Revenue trends, margins, cash flow quality, debt levels, governance signals |
| **Sentiment** | yfinance news feed | News sentiment, analyst rating changes, executive and insider-related signals |
| **Valuation** | yfinance price & volume (3-month) | Price momentum, annualised return & volatility, volume confirmation |
| **Market** | yfinance sector info + Korean peer tickers | Industry cycle, competitive positioning, sector tailwinds/headwinds, peer valuation comparison vs KOSPI |
| **Macro** | yfinance: KRW/USD · KOSPI · KOSDAQ · S&P500 · NASDAQ · US 10Y · Oil · Gold | Currency impact on exporters/importers, interest rate environment, Korea vs global capital flows, commodity cost pressures |

Each agent is independently role-prompted with the chosen risk profile and produces a standalone **BUY / SELL** recommendation before entering the debate phase.

> **Why extend to 5 agents?** The original BlackRock paper used 3 agents and explicitly identified macro and industry analysis as natural extensions. The **Market Agent** contextualises a company within its competitive landscape — a stock trading at fair value in a declining industry is still a risk. The **Macro Agent** captures Korea-specific sensitivities (KRW fluctuations, BOK policy, global capital flows, semiconductor cycles) that no company-level analysis alone can surface.

---

## Debate Mechanism

Inspired by the Round-Robin debate in Zhao et al. (2025), with two prompt-engineering enhancements to produce more substantive disagreement:

```
Round 0 — Independent Analysis  (Steelman enforced)
  All 5 agents analyse in isolation → each issues BUY or SELL
  Before concluding, every agent must write the strongest 2-3 sentence
  argument for the OPPOSITE signal, then explain why their conclusion
  still holds — preventing reflexive, one-sided reasoning.
  If all 5 agree → TERMINATE (unanimous, 0 debate rounds used)

Rounds 1–3 — Structured Debate  (Active challenge enforced)
  Each agent receives the full analyses of all 4 peers
  Agents must identify specific claims in peer analyses that conflict
  with their own data, explain why those claims are wrong or overstated,
  and cite their evidence — passive agreement is not accepted
  Each agent explicitly states: MAINTAINING or CHANGING position, and why
  After each round: if all 5 agree → TERMINATE (unanimous)

After Round 3 — Majority Vote
  3-of-5 wins
  Possible outcomes: 5-0, 4-1, 3-2  (no tie with 5 binary agents)
  Tie-break default: SELL (risk-averse)  /  BUY (risk-neutral)
```

Both risk profiles run **simultaneously** via `ThreadPoolExecutor` — data is fetched once and shared between both runs, halving total wall-clock time.

---

## Risk Profiles

Both profiles are run on every execution and produce separate reports.  
The **only difference** between the two runs is the system prompt given to each agent — the underlying data is identical.

| Behaviour | Risk-Averse | Risk-Neutral |
|---|---|---|
| Ambiguity / tie-break default | **SELL** | **BUY** |
| Volatility treatment | Penalised — high vol leans SELL | Contextual — return must compensate for risk |
| Mixed news sentiment | Lean SELL | Weight evidence, let balance decide |
| Industry uncertainty | Lean SELL | Assess net opportunity vs risk |
| Macro uncertainty | Lean SELL | Assess directional impact on this company |
| Growth vs stability | Stability and capital preservation preferred | Balanced — upside potential weighted equally |
| Steelman requirement | Must argue strongest BUY case before concluding SELL | Must argue strongest SELL case before concluding BUY |
| Debate challenge | Must dispute specific peer claims using fundamental data | Must dispute specific peer claims using fundamental data |

> **Note on prompt engineering:** Both profiles share the same two debate-forcing instructions (`STEELMAN_INSTRUCTION` and `CHALLENGE_INSTRUCTION`) defined once in `base_agent.py` and injected into every agent's prompts. This ensures analytical rigour is profile-independent — what differs is the *weighting* of evidence, not the quality of reasoning.

---

## Project Structure

```
alpha_agents/
│
├── main.py                      # Entry point — prompts for ticker, runs both profiles
├── config.py                    # API keys & model settings
├── requirements.txt
├── .env.example
│
├── agents/
│   ├── base_agent.py            # Claude (primary) + OpenAI (fallback) LLM wrapper
│   │                            #   + STEELMAN_INSTRUCTION and CHALLENGE_INSTRUCTION constants
│   ├── fundamental_agent.py     # OpenDART financial disclosure analysis
│   ├── sentiment_agent.py       # News sentiment analysis
│   ├── valuation_agent.py       # Price / volume / volatility analysis
│   ├── market_agent.py          # Industry cycle, competitive landscape, peer comparison
│   └── macro_agent.py           # KRW/USD, interest rates, KOSPI vs global indices
│
├── tools/
│   ├── dart_tools.py            # OpenDART: corp code registry lookup + financial statements
│   ├── yfinance_tools.py        # Auto-detects .KS/.KQ exchange, fetches price history & news
│   ├── metrics_tools.py         # Annualised return & volatility (paper's exact formulas)
│   ├── market_tools.py          # Sector classification, KOSPI benchmark, Korean peer tickers
│   └── macro_tools.py           # KRW/USD, US yields, global indices, oil, gold
│
├── debate/
│   └── debate_manager.py        # 5-agent round-robin debate + majority vote orchestration
│
├── report/
│   └── report_generator.py      # Structured Markdown report generator
│
└── reports/                     # Auto-created on first run
    ├── 005930_averse_YYYYMMDD_HHMM.md
    └── 005930_neutral_YYYYMMDD_HHMM.md
```

---

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/your-username/alpha-agents.git
cd alpha-agents
```

### 2. Install dependencies
```bash
pip3 install -r requirements.txt
```

### 3. Configure API keys

Copy the example file and fill in your three keys:
```bash
cp .env.example .env
```

```env
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
DART_API_KEY=your_opendart_key
```

| Key | Where to obtain |
|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) → API Keys |
| `DART_API_KEY` | [opendart.fss.or.kr](https://opendart.fss.or.kr) → 인증키 신청/관리 |

---

## Usage

```bash
python3 main.py
```

You will be prompted:
```
============================================================
  AlphaAgents — Korean Equity Analysis
============================================================

  Enter stock ticker (e.g. 005930):
```

Type a 6-digit KRX stock code and press Enter. The system will:

1. **Lookup** the company on OpenDART (auto-resolves stock code → corp code)
2. **Fetch** financial statements (FY current + prior year via OpenDART)
3. **Fetch** price history, news, sector info, and macro indicators (via yfinance)
4. **Run** Risk-Averse and Risk-Neutral agent debates **in parallel**
5. **Save** two Markdown reports to `reports/` and print a terminal summary

### Example tickers

| Ticker | Company | Sector |
|---|---|---|
| `005930` | 삼성전자 (Samsung Electronics) | Technology |
| `000660` | SK하이닉스 (SK Hynix) | Technology |
| `035420` | NAVER | Communication Services |
| `035720` | 카카오 (Kakao) | Communication Services |
| `005380` | 현대자동차 (Hyundai Motor) | Consumer Cyclical |
| `068270` | 셀트리온 (Celltrion) | Healthcare |
| `105560` | KB금융 (KB Financial) | Financial Services |

---

## Output

Two Markdown reports are saved per run, one per risk profile:

```
reports/005930_averse_20260427_1430.md
reports/005930_neutral_20260427_1430.md
```

Each report contains:

| Section | Content |
|---|---|
| Header | Company name, ticker, CEO, analysis date, risk profile |
| Final Recommendation | **BUY / SELL** with consensus type and rounds used |
| Agent Signals Table | Initial signal → final signal per agent, flagging position changes |
| Key Valuation Metrics | Current price, period return, annualised return & volatility, volume |
| Detailed Agent Analyses | Full written analysis from each of the 5 agents (initial round) |
| Debate Log | Complete round-by-round exchange showing how positions evolved |

### Terminal summary example
```
============================================================
 RESULTS — 삼성전자 (005930)
============================================================
 Risk-Averse  : SELL  (Unanimous, 0 round(s))
   Report: reports/005930_averse_20260427_1430.md
 Risk-Neutral : BUY   (Majority, 3 round(s))
   Report: reports/005930_neutral_20260427_1430.md
============================================================
```

---

## LLM Architecture

| Role | Model | Provider |
|---|---|---|
| Primary | `claude-sonnet-4-6` | Anthropic |
| Fallback (auto) | `gpt-4o` | OpenAI |

- If a Claude API call fails for any agent, the system transparently retries with GPT-4o
- Each agent operates independently — no shared memory or state between agents within a round
- Debate context is passed as explicit text, not implicit shared state, preserving full transparency

### Prompt Engineering — Debate Quality

Two shared constants in `base_agent.py` are injected into every agent's prompts to improve analytical depth and genuine disagreement:

| Constant | Injected into | Purpose |
|---|---|---|
| `STEELMAN_INSTRUCTION` | `analyze()` — Round 0 | Forces each agent to construct the strongest possible opposing argument before finalising its recommendation |
| `CHALLENGE_INSTRUCTION` | `update_position()` — Rounds 1–3 | Forces each agent to cite specific conflicting claims from peer analyses and explain why they are wrong — passive agreement is rejected |

These two instructions are profile-agnostic — they apply identically to risk-averse and risk-neutral agents. The risk profile only controls how evidence is *weighted*, not the rigour of the reasoning process.

---

## Key Metrics (from the paper)

**Annualised Cumulative Return**

$$R_{\text{annualized}} = \left(1 + R_{\text{cumulative}}\right)^{\frac{252}{n}} - 1$$

where $n$ = number of trading days in the window.

**Annualised Volatility**

$$\sigma_{\text{annualized}} = \sigma_{\text{daily}} \times \sqrt{252}$$

---

## Macro Indicators Tracked

| Indicator | Ticker | Relevance to Korean Equities |
|---|---|---|
| USD/KRW | `KRW=X` | Weaker KRW boosts export revenues; stronger KRW pressures them |
| KOSPI | `^KS11` | Benchmark for Korean large-cap performance |
| KOSDAQ | `^KQ11` | Benchmark for Korean tech/growth equities |
| S&P 500 | `^GSPC` | Global risk appetite; divergence from KOSPI signals Korea-specific risk |
| NASDAQ | `^IXIC` | Relevant for tech-sector correlation |
| US 10Y Treasury | `^TNX` | Higher yields attract capital away from EM markets including Korea |
| Gold | `GC=F` | Safe-haven flows; inversely correlated with risk appetite |
| Crude Oil (WTI) | `CL=F` | Cost input for industrials; geopolitical risk proxy |

---

## Limitations

- **News coverage:** yfinance news is sparse for smaller KOSPI/KOSDAQ stocks. The Sentiment Agent may receive limited data for mid/small-cap names.
- **Financial data lag:** OpenDART financials reflect the most recently filed annual report — typically the prior completed fiscal year.
- **Industry peer mapping:** Sector peer tickers are predefined for major Korean sectors. Niche or cross-sector companies may not have ideal peer comparisons.
- **No portfolio optimisation:** This system outputs BUY/SELL signals only. Portfolio construction, weighting, and diversification are out of scope.
- **LLM hallucination:** Despite the multi-agent debate mechanism — which demonstrably reduces hallucination (Du et al., 2023) — outputs should be treated as research assistance, not financial advice.

---

## References

> Zhao, T., Lyu, J., Jones, S., Garber, H., Pasquali, S., & Mehta, D. (2025).  
> *AlphaAgents: Large Language Model based Multi-Agents for Equity Portfolio Constructions.*  
> BlackRock, Inc. arXiv:2508.11152

> Du, Y., Li, S., Torralba, A., Tenenbaum, J. B., & Mordatch, I. (2023).  
> *Improving factuality and reasoning in language models through multiagent debate.*  
> arXiv:2305.14325

---

## Disclaimer

> This system is built for **academic and research purposes only.**  
> It does not constitute financial advice. Past signals generated by this system do not guarantee future performance. Always conduct your own due diligence before making any investment decisions.

---

*Built with Claude (Anthropic) · OpenAI · OpenDART · yfinance*
