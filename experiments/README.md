# Experiments

A thin research harness that drives the existing analysis pipeline from the
outside to compare conditions systematically. It does **not** change the main
analyze → portfolio → backtest → report flow — it just runs it many times with
different settings and records the results.

## Workflow

```
1. Make a recipe   →  run experiment                          (guided Q&A)
                      or copy recipes/_template.yaml and edit by hand
2. Dry-run (free)  →  DEBUG_MODE=true run experiment <name>    (stubbed LLM)
3. Run it          →  run experiment <name>                    (asks to confirm cost)
4. Read results    →  experiments/results/<name>_<date>.csv
```

(`run experiment` maps to `python3 main.py experiment`; you can also call
`python3 experiments/new_experiment.py` / `python3 experiments/runner.py <name>`
directly.)

## What the runner does

For each stock it fetches data **once** (data is deterministic for a stock +
as-of date), then runs the debate once per *(condition × repeat)* — the debate
is the stochastic, LLM-driven part, which is what `repeats` samples. It does
**not** write per-run report files; the only output is one results CSV, so a
large sweep doesn't flood `reports/`.

Each CSV row is one *(stock × condition × repeat × profile)* outcome, with
provenance for reproducibility: `signal, conviction, consensus_type/round,
agents, model, debug, git_sha, run_ts`. The runner also prints an averaged
summary (BUY rate, mean conviction, ± std) so the repeats actually pay off.

A `DEBUG_MODE=true` run stubs the LLM (free, fast) and still fetches real data —
use it to validate a recipe and see the run counts before paying for it.

## What a recipe is

One YAML file = one experiment = the *design*, written down before you run so
the result is reproducible. It declares:

- **stocks**, **as_of** date, **profiles** — held the same across the experiment
- **repeats** — how many times to run each setup (the debate is an LLM and varies
  run-to-run, so repeats let you average out the noise)
- **conditions** — the setups being compared, each an **odd-sized** agent subset

See `recipes/_template.yaml` for the annotated format.

## Notes

- Stock codes are checked for shape (6 digits) only when building a recipe; they
  are looked up for real at run time.
- Agent counts must be odd (1/3/5) so the majority vote can't tie — the builder
  enforces this.
- `results/` is generated output (gitignored).
