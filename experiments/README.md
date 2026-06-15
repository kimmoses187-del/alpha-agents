# Experiments

A thin research harness that drives the existing analysis pipeline from the
outside to compare conditions systematically. It does **not** change the main
analyze → portfolio → backtest → report flow — it just runs it many times with
different settings and records the results.

## Workflow

```
1. Make a recipe   →  run experiment                          (guided Q&A)
                      or copy recipes/_template.yaml and edit by hand
2. Run it          →  (runner — coming next)
3. Read results    →  experiments/results/<name>_<date>.csv
```

(`run experiment` maps to `python3 main.py experiment`; you can also call
`python3 experiments/new_experiment.py` directly.)

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
