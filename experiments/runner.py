"""
experiments/runner.py
=====================
Executes an experiment recipe and writes a results CSV.

Run:
    run experiment <recipe>              # e.g. run experiment macro-ablation
    DEBUG_MODE=true run experiment <recipe>   # free dry-run (stubbed LLM)
    python3 experiments/runner.py <recipe>    # equivalent, direct

<recipe> is a name under experiments/recipes/ (with or without .yaml) or a path.

What it does
------------
For each stock it fetches data ONCE (data is deterministic for a given stock +
as-of date), then runs the debate once per (condition × repeat). The debate is
the stochastic, LLM-driven part — that's what repeats sample. Per-run report
files are NOT written; the only output is one results CSV with provenance, so a
big sweep doesn't flood reports/.

Each CSV row = one (stock × condition × repeat × profile) outcome.
"""

import csv
import io
import os
import sys
import subprocess
from contextlib import redirect_stdout
from datetime import datetime
from statistics import mean, pstdev

# Make the project root importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

from config import (CLAUDE_MODEL, DEBUG_MODE, ALL_AGENTS, ALL_PROFILES,
                    profile_label, agent_label)
from tools.dart_tools import lookup_company
from orchestrator.orchestrator_agent import OrchestratorAgent
from portfolio.portfolio_agent import compute_conviction

_HERE        = os.path.dirname(os.path.abspath(__file__))
RECIPES_DIR  = os.path.join(_HERE, "recipes")
RESULTS_DIR  = os.path.join(_HERE, "results")

# Very rough ballpark for a one-profile debate (all agents, with prompt caching).
# Scales with agent count. Used only for the pre-run estimate, never billed.
_EST_COST_PER_AGENT_DEBATE = 0.008


# ── Recipe loading + validation ───────────────────────────────────────────────

def _resolve_recipe_path(recipe: str) -> str:
    """Accept a bare name, a name.yaml, or a full path."""
    candidates = [recipe,
                  os.path.join(RECIPES_DIR, recipe),
                  os.path.join(RECIPES_DIR, f"{recipe}.yaml"),
                  os.path.join(RECIPES_DIR, f"{recipe}.yml")]
    for c in candidates:
        if os.path.isfile(c):
            return c
    raise FileNotFoundError(
        f"Recipe '{recipe}' not found. Looked in {RECIPES_DIR}/. "
        f"Available: {', '.join(_list_recipes()) or '(none)'}"
    )


def _list_recipes() -> list:
    if not os.path.isdir(RECIPES_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(RECIPES_DIR)
                  if f.endswith(".yaml") and not f.startswith("_"))


def _validate_recipe(r: dict) -> None:
    """Raise ValueError with a plain-English message on any problem.
    Recipes can be hand-edited, so never trust them blindly."""
    errors = []

    if not r.get("name"):
        errors.append("missing 'name'")

    stocks = r.get("stocks") or []
    if not stocks:
        errors.append("'stocks' is empty")
    for s in stocks:
        if not (isinstance(s, str) and s.isdigit() and len(s) == 6):
            errors.append(f"stock '{s}' is not a 6-digit code (quote it: \"{s}\")")

    try:
        datetime.strptime(str(r.get("as_of", "")), "%Y/%m/%d")
    except ValueError:
        errors.append(f"'as_of' must be YYYY/MM/DD, got {r.get('as_of')!r}")

    profiles = r.get("profiles") or []
    if not profiles:
        errors.append("'profiles' is empty")
    for p in profiles:
        if p not in ALL_PROFILES:
            errors.append(f"unknown profile '{p}' (use {', '.join(ALL_PROFILES)})")

    reps = r.get("repeats")
    if not isinstance(reps, int) or reps < 1:
        errors.append(f"'repeats' must be a whole number ≥ 1, got {reps!r}")

    conditions = r.get("conditions") or []
    if not conditions:
        errors.append("'conditions' is empty — define at least one setup")
    seen = set()
    for i, c in enumerate(conditions, 1):
        cname = c.get("name") or f"#{i}"
        if cname in seen:
            errors.append(f"duplicate condition name '{cname}'")
        seen.add(cname)
        agents = c.get("agents") or []
        unknown = [a for a in agents if a not in ALL_AGENTS]
        if unknown:
            errors.append(f"condition '{cname}': unknown agent(s) {unknown}")
        if len(agents) == 0:
            errors.append(f"condition '{cname}': no agents")
        elif len(agents) % 2 == 0:
            errors.append(f"condition '{cname}': {len(agents)} agents is EVEN — "
                          "must be odd (1/3/5) so the vote can't tie")

    if errors:
        raise ValueError("Recipe is invalid:\n  - " + "\n  - ".join(errors))


def _load_recipe(recipe: str) -> dict:
    path = _resolve_recipe_path(recipe)
    with open(path, encoding="utf-8") as f:
        r = yaml.safe_load(f)
    # Defensive coercion: codes must be strings (in case the YAML lost quotes).
    r["stocks"] = [str(s) for s in (r.get("stocks") or [])]
    # Canonicalise agent order per condition.
    for c in (r.get("conditions") or []):
        c["agents"] = [a for a in ALL_AGENTS if a in (c.get("agents") or [])]
    _validate_recipe(r)
    r["_path"] = path
    return r


# ── Helpers ───────────────────────────────────────────────────────────────────

def _git_sha() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=_HERE, capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _quiet():
    """Swallow the pipeline's own prints so batch progress stays readable."""
    return redirect_stdout(io.StringIO())


def _plan(recipe: dict) -> dict:
    n_stocks = len(recipe["stocks"])
    n_reps   = recipe["repeats"]
    n_prof   = len(recipe["profiles"])
    conds    = recipe["conditions"]
    debates  = n_stocks * len(conds) * n_reps            # one _run_debates call each
    rows     = debates * n_prof
    est_cost = sum(len(c["agents"]) * _EST_COST_PER_AGENT_DEBATE
                   for c in conds) * n_stocks * n_reps * n_prof
    return {"debates": debates, "rows": rows, "est_cost": est_cost}


# ── Execution ─────────────────────────────────────────────────────────────────

def run_recipe(recipe: dict, confirm: bool = True) -> str:
    name      = recipe["name"]
    stocks    = recipe["stocks"]
    as_of     = datetime.strptime(recipe["as_of"], "%Y/%m/%d")
    profiles  = list(recipe["profiles"])
    repeats   = recipe["repeats"]
    conditions = recipe["conditions"]

    plan = _plan(recipe)
    print(f"\n{'='*60}")
    print(f"  EXPERIMENT: {name}")
    if recipe.get("question"):
        print(f"  Question  : {recipe['question']}")
    print(f"{'='*60}")
    print(f"  Stocks {len(stocks)} × Conditions {len(conditions)} × "
          f"Repeats {repeats} × Profiles {len(profiles)}")
    print(f"  → {plan['debates']} debates, {plan['rows']} result rows")
    if DEBUG_MODE:
        print(f"  MODE: DEBUG dry-run — LLM stubbed, no cost.")
    else:
        print(f"  Est. cost: ~${plan['est_cost']:.2f}  (very rough)")
        if confirm:
            ans = input("\n  Proceed with the REAL run? (y/N): ").strip().lower()
            if ans != "y":
                print("  Cancelled.")
                return ""

    orch    = OrchestratorAgent()
    rows    = []
    run_ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sha     = _git_sha()
    noop_cb = lambda *a, **k: None   # suppresses the live debate grid

    for code in stocks:
        # ── Fetch data ONCE per stock ──
        print(f"\n  ── {code} ──  fetching data...", flush=True)
        try:
            with _quiet():
                corp_info = lookup_company(code)
                data      = orch._fetch_data(code, as_of, corp_info)
            company = corp_info["corp_name"]
        except Exception as e:
            print(f"  ⚠ {code}: data fetch failed ({e}) — skipping.")
            continue

        for cond in conditions:
            agents = cond["agents"]
            for rep in range(1, repeats + 1):
                try:
                    with _quiet():
                        debate_results = orch._run_debates(
                            company, data, progress_cb=noop_cb,
                            profiles=profiles, agents=agents)
                except Exception as e:
                    print(f"  ⚠ {code} [{cond['name']} rep {rep}] debate failed ({e})")
                    continue

                sig_summary = []
                for prof in profiles:
                    dr   = debate_results[prof]
                    conv = compute_conviction(dr)
                    rows.append({
                        "experiment":      name,
                        "condition":       cond["name"],
                        "stock":           code,
                        "company":         company,
                        "profile":         prof,
                        "repeat":          rep,
                        "signal":          dr["final_signal"],
                        "conviction":      conv,
                        "consensus_type":  dr["consensus_type"],
                        "consensus_round": dr["consensus_round"],
                        "agents":          "|".join(agents),
                        "n_agents":        len(agents),
                        "as_of":           recipe["as_of"],
                        "model":           "DEBUG" if DEBUG_MODE else CLAUDE_MODEL,
                        "debug":           DEBUG_MODE,
                        "git_sha":         sha,
                        "run_ts":          run_ts,
                    })
                    sig_summary.append(f"{profile_label(prof)}:{dr['final_signal']}({conv:.2f})")
                print(f"    [{cond['name']:<12} rep {rep}/{repeats}] {code} → "
                      + "  ".join(sig_summary))

    if not rows:
        print("\n  No results produced (all stocks/debates failed).")
        return ""

    # ── Write CSV ──
    os.makedirs(RESULTS_DIR, exist_ok=True)
    tag      = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_path = os.path.join(RESULTS_DIR, f"{name}_{tag}.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    _print_summary(rows, conditions, profiles)
    print(f"\n  ✓ {len(rows)} rows → {os.path.relpath(out_path)}")
    return out_path


def _print_summary(rows: list, conditions: list, profiles: list) -> None:
    """Averaged view per (condition, profile) — the payoff of repeats."""
    print(f"\n{'-'*60}")
    print("  SUMMARY  (averaged over repeats × stocks)")
    print(f"{'-'*60}")
    print(f"  {'condition':<14}{'profile':<14}{'BUY rate':>9}{'avg conv':>10}{'± std':>8}")
    for cond in conditions:
        for prof in profiles:
            sub = [r for r in rows
                   if r["condition"] == cond["name"] and r["profile"] == prof]
            if not sub:
                continue
            buy_rate = sum(1 for r in sub if r["signal"] == "BUY") / len(sub)
            convs    = [r["conviction"] for r in sub]
            print(f"  {cond['name']:<14}{profile_label(prof):<14}"
                  f"{buy_rate*100:>7.0f}% {mean(convs):>9.2f}"
                  f"{pstdev(convs) if len(convs) > 1 else 0.0:>8.2f}")


# ── Entry ─────────────────────────────────────────────────────────────────────

def main(recipe_arg: str = None) -> None:
    if not recipe_arg:
        print("  Usage: run experiment <recipe-name>")
        print(f"  Available recipes: {', '.join(_list_recipes()) or '(none — build one with `run experiment`)'}")
        sys.exit(1)
    try:
        recipe = _load_recipe(recipe_arg)
    except (FileNotFoundError, ValueError) as e:
        print(f"\n  ✗ {e}")
        sys.exit(1)
    run_recipe(recipe)


if __name__ == "__main__":
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else None)
    except (KeyboardInterrupt, EOFError):
        print("\n  Cancelled.")
        sys.exit(1)
