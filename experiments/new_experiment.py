"""
experiments/new_experiment.py
=============================
Guided builder for an experiment recipe (Version 1 — ask & answer).

Run:
    run experiment            (preferred — via main.py's `experiment` subcommand)
    python3 experiments/new_experiment.py   (equivalent, direct)

It asks a handful of questions in the terminal and writes a recipe YAML to
experiments/recipes/<name>.yaml. The recipe is the *design*: it records exactly
what will be tested so a run is reproducible. The separate runner (next step)
reads the recipe and executes it.

This script is intentionally lightweight — it imports only `config`, never the
analysis pipeline, so it starts instantly and stays offline. Stock codes are
checked for shape (6 digits) only; they are looked up for real at run time.
"""

import os
import re
import sys
from datetime import datetime

# Make the project root importable when run as `python3 experiments/new_experiment.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

from config import ALL_AGENTS, ALL_PROFILES, agent_label, profile_label

RECIPES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recipes")


def _quote_digit_strings(dumper, data):
    """Force all-digit strings (stock codes) to be quoted so a code like
    '207940' round-trips as a string instead of being read back as an int."""
    style = "'" if data.isdigit() else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


yaml.add_representer(str, _quote_digit_strings, Dumper=yaml.SafeDumper)


# ── Small input helpers ───────────────────────────────────────────────────────

def _safe_name(name: str) -> str:
    """kebab-case, filesystem-safe."""
    name = re.sub(r"[^\w\s-]", "", name.strip().lower())
    name = re.sub(r"[\s_]+", "-", name).strip("-")
    return name or "experiment"


def _ask_stocks() -> list:
    while True:
        raw = input("\n  Stocks — 6-digit codes, comma-separated (e.g. 005930, 000660): ").strip()
        codes = [c.strip() for c in raw.split(",") if c.strip()]
        if not codes:
            print("  Enter at least one stock code.")
            continue
        bad = [c for c in codes if not re.fullmatch(r"\d{6}", c)]
        if bad:
            print(f"  These aren't 6-digit codes: {', '.join(bad)}  "
                  "(e.g. Samsung is 005930 — keep the leading zeros).")
            continue
        # De-duplicate, preserve order
        seen, unique = set(), []
        for c in codes:
            if c not in seen:
                seen.add(c)
                unique.append(c)
        return unique


def _ask_date() -> str:
    while True:
        raw = input("\n  Analysis (as-of) date — YYYY/MM/DD: ").strip()
        try:
            datetime.strptime(raw, "%Y/%m/%d")
            return raw
        except ValueError:
            print("  Invalid format. Use YYYY/MM/DD (e.g. 2025/06/01).")


def _ask_profiles() -> list:
    both = len(ALL_PROFILES) + 1
    print("\n  Which risk profile(s) should every run use?")
    for i, p in enumerate(ALL_PROFILES, 1):
        print(f"    [{i}] {profile_label(p)} only")
    print(f"    [{both}] Both  (default)")
    while True:
        raw = input(f"  Choice (1–{both}) [default {both}]: ").strip()
        if raw == "":
            return list(ALL_PROFILES)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(ALL_PROFILES):
                return [ALL_PROFILES[n - 1]]
            if n == both:
                return list(ALL_PROFILES)
        print(f"  Please enter a number from 1 to {both}.")


def _ask_repeats() -> int:
    print("\n  How many times to repeat each setup?")
    print("  (The debate is an LLM and varies run-to-run, so repeats let you")
    print("   average out the noise. 1 = no averaging; 5 is a reasonable start.)")
    while True:
        raw = input("  Repeats [default 5]: ").strip()
        if raw == "":
            return 5
        if raw.isdigit() and int(raw) >= 1:
            return int(raw)
        print("  Enter a whole number ≥ 1.")


def _ask_agents(label: str) -> list:
    """Pick an ODD-sized subset of the agents for one condition."""
    print(f"\n    Agents for setup '{label}':")
    for i, a in enumerate(ALL_AGENTS, 1):
        print(f"      [{i}] {agent_label(a)}")
    print("      [A] All five")
    print("    Pick an ODD number (1, 3, or 5) so the majority vote can't tie.")
    while True:
        raw = input("    Enter agent numbers (e.g. 1,3,5) or A: ").strip().upper()
        if raw == "A":
            return list(ALL_AGENTS)
        try:
            idxs = [int(x) for x in raw.split(",") if x.strip()]
        except ValueError:
            print("    Invalid input — use numbers like 1,3,5.")
            continue
        if any(i < 1 or i > len(ALL_AGENTS) for i in idxs):
            print(f"    Numbers must be between 1 and {len(ALL_AGENTS)}.")
            continue
        chosen = [a for a in ALL_AGENTS if ALL_AGENTS.index(a) + 1 in idxs]
        if not chosen:
            print("    Select at least one agent.")
            continue
        if len(chosen) % 2 == 0:
            print(f"    You picked {len(chosen)} agents — that's even and could tie. "
                  "Pick an odd number (1, 3, or 5).")
            continue
        return chosen


def _ask_conditions() -> list:
    print("\n  Now define the setups to compare. Each setup is one variation")
    print("  (e.g. 'all_five' vs 'no_macro'). You need at least one.")
    conditions, used_names = [], set()
    while True:
        n = len(conditions) + 1
        name = input(f"\n  Setup #{n} name (e.g. all_five): ").strip()
        name = _safe_name(name) if name else f"setup-{n}"
        if name in used_names:
            print(f"  '{name}' already used — pick a different name.")
            continue
        agents = _ask_agents(name)
        conditions.append({"name": name, "agents": agents})
        used_names.add(name)

        more = input(f"\n  Add another setup? (Y/N) [{len(conditions)} so far]: ").strip().upper()
        if more != "Y":
            break
    return conditions


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 60)
    print("  K-AlphaAgents — New Experiment Recipe")
    print("=" * 60)
    print("  Answer the questions; this writes a recipe YAML you can run later.")

    name     = _safe_name(input("\n  Experiment name: ").strip())
    question = input("  One-line research question (optional): ").strip()
    stocks   = _ask_stocks()
    as_of    = _ask_date()
    profiles = _ask_profiles()
    repeats  = _ask_repeats()
    conditions = _ask_conditions()

    recipe = {
        "name":       name,
        "question":   question,
        "stocks":     stocks,
        "as_of":      as_of,
        "profiles":   profiles,
        "repeats":    repeats,
        "conditions": conditions,
    }

    os.makedirs(RECIPES_DIR, exist_ok=True)
    path = os.path.join(RECIPES_DIR, f"{name}.yaml")
    if os.path.exists(path):
        ow = input(f"\n  {path} already exists. Overwrite? (Y/N): ").strip().upper()
        if ow != "Y":
            print("  Cancelled — nothing written.")
            return

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Experiment recipe — generated {datetime.now():%Y-%m-%d %H:%M}\n")
        f.write("# Edit by hand any time, or re-run new_experiment.py.\n\n")
        yaml.safe_dump(recipe, f, sort_keys=False, allow_unicode=True, default_flow_style=False)

    # ── Summary ──
    total_runs = len(conditions) * repeats * len(stocks)
    print("\n" + "-" * 60)
    print(f"  ✓ Saved recipe → {os.path.relpath(path)}")
    print(f"  Conditions: {len(conditions)}  ·  Repeats: {repeats}  ·  Stocks: {len(stocks)}")
    print(f"  Profiles per run: {', '.join(profile_label(p) for p in profiles)}")
    print(f"  → {total_runs} stock-analysis runs "
          f"({len(conditions)} setups × {repeats} repeats × {len(stocks)} stocks)")
    if total_runs >= 30:
        print(f"  ⚠️  That's a lot of runs — dry-run with DEBUG_MODE first to estimate cost.")
    print("-" * 60)
    print("  Next:")
    print(f"    DEBUG_MODE=true run experiment {name}   # free dry-run first")
    print(f"    run experiment {name}                   # real run")
    print(f"  Or open {os.path.relpath(path)} to tweak it by hand.\n")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n  Cancelled.")
        sys.exit(1)
