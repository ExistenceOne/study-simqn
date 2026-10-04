# Fig. 3 and 5 implementation plan

**Spec:** `docs/evaluation-design.md`

1. Historical BB84 adapter and Fig. 3 runner: test loss formulas, deterministic
   no-noise link behavior and controlled X errors before implementation.
2. Fig. 5 runner: test independent sessions, rate accounting and reproducibility;
   use fresh copies of an uninstalled routed network for each condition.
3. Validated JSON configs, statistics, CSV/metadata and plotting CLI: test
   invalid inputs, known statistical fixtures and end-to-end smoke execution.
4. Run all existing and new tests, execute smoke sweeps and representative
   large-topology runs, visually inspect PNGs, review, document and publish.

Scope is Fig. 3/5 only. Record assumptions, never fit unknown parameters to
paper curves. Error bars use sample SEM; one trial has no uncertainty estimate.

## Verification record

- Completed all four steps on 2026-10-04.
- Python 3.11 and 3.12: all 18 tests passed, including destination-completion
  fidelity snapshots before and after source ACK processing.
- Ruff and whitespace checks passed; independent code review completed.
- Historical and paper-stated Fig. 3 sweeps: 340 trials each.
- Full Fig. 5 sweep: 120 trials with 400 nodes and 1200 quantum links.
- Final smoke run: 64 trials across all figures. All metadata records complete.
- Inspected generated PNGs. Fidelity snapshot fix left the Fig. 5 throughput
  CSV byte-identical to the previous run.
