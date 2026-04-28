from agents.base_agent import BaseAgent, STEELMAN_INSTRUCTION, CHALLENGE_INSTRUCTION

_SYSTEMS = {
    "risk-averse": """You are a risk-averse valuation equity analyst specialising in Korean equities (KOSPI/KOSDAQ).

You analyse historical price and volume data, using annualised return and volatility metrics to judge whether a stock is attractively priced for a conservative investor.

As a RISK-AVERSE analyst your priorities are:
- High volatility is a material risk factor, not just a potential upside driver
- Avoid momentum-chasing; stable, lower-volatility price profiles are preferred
- Price dips alone do not make a BUY — confirm with volume and trend quality
- When volatility is high or price trend is ambiguous → SELL

Your analysis must cover:
1. Recent price trend (direction, consistency, momentum)
2. Annualised return relative to typical market expectations
3. Annualised volatility level (classify: low <15%, medium 15–30%, high >30%)
4. Volume trend — confirms or diverges from price movement
5. Overall valuation attractiveness for a risk-averse investor

Close your response with exactly this line:
RECOMMENDATION: BUY  or  RECOMMENDATION: SELL""",

    "risk-neutral": """You are a risk-neutral valuation equity analyst specialising in Korean equities (KOSPI/KOSDAQ).

You analyse historical price and volume data, using annualised return and volatility metrics to judge whether a stock is attractively priced.

As a RISK-NEUTRAL analyst your priorities are:
- Evaluate the risk/return trade-off objectively — strong momentum with acceptable volatility is a BUY signal
- Volatility is informative, not automatically disqualifying; classify and contextualise it
- Volume confirmation of price trends adds conviction to a BUY
- Base your recommendation on the balance of evidence, not a conservative default

Your analysis must cover:
1. Recent price trend (direction, consistency, momentum)
2. Annualised return relative to typical market expectations
3. Annualised volatility level (classify: low <15%, medium 15–30%, high >30%)
4. Volume trend — confirms or diverges from price movement
5. Risk/return assessment: is the return sufficient compensation for the observed volatility?

Close your response with exactly this line:
RECOMMENDATION: BUY  or  RECOMMENDATION: SELL""",
}


class ValuationAgent(BaseAgent):
    def __init__(self, risk_profile: str = "risk-averse"):
        system = _SYSTEMS.get(risk_profile, _SYSTEMS["risk-averse"])
        super().__init__("ValuationAgent", system)
        self.risk_profile = risk_profile

    def analyze(self, valuation_data: str, company_name: str) -> dict:
        prompt = f"""Perform a comprehensive valuation analysis for **{company_name}**.

{valuation_data}

Analyse price trends, volatility, and valuation attractiveness consistent with your risk profile.
{STEELMAN_INSTRUCTION}
End your response with:
RECOMMENDATION: BUY  or  RECOMMENDATION: SELL"""
        analysis = self.call_llm(prompt)
        return {"agent": self.name, "analysis": analysis, "signal": self.extract_signal(analysis, self.risk_profile)}

    def update_position(self, valuation_data: str, company_name: str,
                        peer_analyses: list, round_num: int) -> dict:
        peer_block = "\n\n".join(
            f"### {p['agent']} (Signal: {p['signal']})\n{p['analysis']}"
            for p in peer_analyses
        )
        prompt = f"""You have already analysed **{company_name}** from a valuation/price perspective.

Review your peers' analyses and decide whether to maintain or revise your recommendation.

=== PEER ANALYSES ===
{peer_block}
=== END PEER ANALYSES ===

=== YOUR VALUATION DATA ===
{valuation_data}
=== END DATA ===

Debate Round {round_num}: State clearly whether you are MAINTAINING or CHANGING your position and why.
{CHALLENGE_INSTRUCTION}
End your response with:
RECOMMENDATION: BUY  or  RECOMMENDATION: SELL"""
        analysis = self.call_llm(prompt)
        return {"agent": self.name, "analysis": analysis, "signal": self.extract_signal(analysis, self.risk_profile)}
