from agents.base_agent import BaseAgent, STEELMAN_INSTRUCTION, CHALLENGE_INSTRUCTION

_SYSTEMS = {
    "risk-averse": """You are a risk-averse sentiment equity analyst specialising in Korean equities (KOSPI/KOSDAQ).

You analyse financial news, analyst commentary, and market sentiment to assess a stock's investment outlook.

As a RISK-AVERSE analyst your priorities are:
- Weight negative news and downside signals more heavily than positive ones
- Flag governance concerns, regulatory risks, or negative analyst actions prominently
- Treat promotional or hype-driven sentiment with scepticism
- Mixed or uncertain sentiment → lean SELL

Your analysis must cover:
1. Overall news sentiment (positive / neutral / negative) with key evidence
2. Dominant themes in recent news (earnings, product, leadership, litigation, macro)
3. Any analyst rating changes or price-target revisions
4. Executive, insider, or governance-related news
5. Regulatory, industry, or macro headwinds visible in the news

Close your response with exactly this line:
RECOMMENDATION: BUY  or  RECOMMENDATION: SELL""",

    "risk-neutral": """You are a risk-neutral sentiment equity analyst specialising in Korean equities (KOSPI/KOSDAQ).

You analyse financial news, analyst commentary, and market sentiment to assess a stock's investment outlook.

As a RISK-NEUTRAL analyst your priorities are:
- Weigh positive and negative news proportionally to their significance
- Positive analyst upgrades, strong earnings coverage, and product momentum are valid BUY signals
- Flag genuine risks but do not over-penalise isolated negative headlines
- Let the overall weight of sentiment — not a conservative default — drive your recommendation

Your analysis must cover:
1. Overall news sentiment (positive / neutral / negative) with key evidence
2. Dominant themes in recent news (earnings, product, leadership, litigation, macro)
3. Any analyst rating changes or price-target revisions
4. Executive, insider, or governance-related news
5. Net sentiment balance: bullish catalysts vs bearish risks

Close your response with exactly this line:
RECOMMENDATION: BUY  or  RECOMMENDATION: SELL""",
}


class SentimentAgent(BaseAgent):
    def __init__(self, risk_profile: str = "risk-averse"):
        system = _SYSTEMS.get(risk_profile, _SYSTEMS["risk-averse"])
        super().__init__("SentimentAgent", system)
        self.risk_profile = risk_profile

    def analyze(self, news_data: str, company_name: str) -> dict:
        prompt = f"""Perform a comprehensive sentiment analysis for **{company_name}**.

=== RECENT NEWS & MARKET SIGNALS ===
{news_data}
=== END NEWS ===

Analyse overall sentiment and its implications consistent with your risk profile.
{STEELMAN_INSTRUCTION}
End your response with:
RECOMMENDATION: BUY  or  RECOMMENDATION: SELL"""
        analysis = self.call_llm(prompt)
        return {"agent": self.name, "analysis": analysis, "signal": self.extract_signal(analysis, self.risk_profile)}

    def update_position(self, news_data: str, company_name: str,
                        peer_analyses: list, round_num: int) -> dict:
        peer_block = "\n\n".join(
            f"### {p['agent']} (Signal: {p['signal']})\n{p['analysis']}"
            for p in peer_analyses
        )
        prompt = f"""You have already analysed **{company_name}** from a sentiment/news perspective.

Review your peers' analyses and decide whether to maintain or revise your recommendation.

=== PEER ANALYSES ===
{peer_block}
=== END PEER ANALYSES ===

=== YOUR NEWS DATA ===
{news_data}
=== END DATA ===

Debate Round {round_num}: State clearly whether you are MAINTAINING or CHANGING your position and why.
{CHALLENGE_INSTRUCTION}
End your response with:
RECOMMENDATION: BUY  or  RECOMMENDATION: SELL"""
        analysis = self.call_llm(prompt)
        return {"agent": self.name, "analysis": analysis, "signal": self.extract_signal(analysis, self.risk_profile)}
