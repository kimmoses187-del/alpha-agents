import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
DART_API_KEY      = os.getenv("DART_API_KEY")

CLAUDE_MODEL      = "claude-sonnet-4-6"
OPENAI_MODEL      = "gpt-4o"
MAX_DEBATE_ROUNDS = 3
