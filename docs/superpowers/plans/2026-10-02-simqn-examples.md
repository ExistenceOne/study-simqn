# SimQN examples implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement the tasks inline.

**Goal:** Ship five runnable beginner examples with Korean explanations to the user's repository.

**Architecture:** Standalone scripts call SimQN directly. Only CLI validation is shared; real subprocess integration tests exercise the published commands.

**Tech Stack:** Python 3.11+, qns 0.2.3, NumPy, Pandas, unittest.

**Spec:** `docs/design.md`

## Global Constraints

- Pin the tested dependency versions; no upstream source vendoring.
- Emit JSON; stochastic examples default to seed 42.
- Keep examples small enough to read and run locally.

## Review Focus

- Invalid/NaN numeric input must produce an argparse error.
- Loss 0/1 must deliver all/no qubits without simulation-window artifacts.
- Repeated seed must reproduce sampled results.
- Route costs must represent the chosen metric, not a simulated delivery time.
- Zero completed entanglements must produce null fidelity, not a division error.

## Task 1: Examples and behavioral tests

**Files:** `examples/*.py`, `tests/test_examples.py`, `requirements.txt`

**Interfaces:** Each example is a CLI producing one JSON object. CLI validators convert bounded numeric inputs or raise argparse.ArgumentTypeError.

- [x] Write subprocess tests for event order, measurement statistics/correlation, channel endpoints, two different routes, successful and unfinished distribution, invalid inputs and seeds.
- [x] Run unittest; confirm examples fail because scripts do not yet exist.
- [x] Implement scripts directly against installed qns 0.2.3 APIs.
- [x] Run unittest and all five default commands; confirm physical expectations.

## Task 2: Teaching material and publishing

**Files:** `README.md`, `docs/sample-results.json`, `.github/workflows/examples.yml`, `LICENSE`

**Interfaces:** Document the CLIs from Task 1, using captured output from actual runs.

- [x] Explain every experiment, assumptions, units and parameter variations in Korean.
- [x] Add CI running the unittest suite on Python 3.11 and 3.12.
- [x] Review source and README, verify in a second clean environment.
- [x] Commit, fast-forward the user's repository main branch and verify remote commit.

## Verification record

- Python 3.11.16 and 3.12.14: 9 unittest tests passed in each environment.
- Ruff: all checks passed.
- Five default examples and all README entanglement parameter variations executed successfully.
- Independent code review found no blocking issues. Extremely small send-rate now returns a CLI error.
- Initial implementation commit `1ab8751` published to GitHub main and remote SHA verified.
