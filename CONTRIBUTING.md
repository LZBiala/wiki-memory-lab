# Contributing

Thanks for looking. This repo is small on purpose; contributions that keep it
small, honest, and reproducible are welcome.

## Setup and tests (no keys, stdlib-only runtime)

```
git clone <this-repo> && cd wiki-memory-lab
pip install -e ".[dev]"        # runtime is stdlib-only; the dev extra is pytest
pytest -q                      # the contract suite
python tools/blocklist_check.py    # the repo hygiene gate
python -m wikimemlab demo --quiet  # regenerate every published artifact
git diff --exit-code           # the drift gate: a clean tree means no claim drifted
```

That sequence is exactly what CI runs (Windows + Linux, pinned Python 3.12).
Run it before opening a PR; a red gate locally will be a red gate in CI.

## What PRs are welcome

- **New adversarial fixtures** — tasks or corpora that push the title matcher,
  the scorer, or the decay rule into a failure direction not yet counted.
- **New probe tasks with ground-truth labels** — retrieval cases the one-line
  hooks should (or measurably cannot) recover.
- **New measured defect classes** — a failure mode the harness could count
  honestly, with the counting logic and its caveat in the same change.
- **Documentation fixes** that make a claim clearer without making it bigger.

Changes that alter any published number must regenerate the committed
artifacts in the same PR — otherwise the drift gate fails, on purpose.

## House law

Every published number must regenerate in CI - the build fails if a claim
drifts. Live-model results never enter drift-gated sections. The hygiene gate
must pass.
