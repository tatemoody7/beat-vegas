# scripts/archive: the closed studies

Moved here 2026-10-18 (final-2026 plan PR-19). Each script produced its result and
the question is closed; nothing live imports from here, no workflow runs them (they
left `study.yml`'s menu), and no registry row changed with the move. They stay
runnable for the record: run one from the repo root with `PYTHONPATH=. python
scripts/archive/<name>.py --help`. `tests/test_archive_scripts.py` keeps every file
compiling.

The shared code each one called lives in `beatvegas/` (mostly `beatvegas/backtest/`);
only the command-line wrappers moved. Rows are in `docs/HYPOTHESES.md`.

| script | registry row(s) | verdict | where the result is |
|---|---|---|---|
| `blend_gate.py` | H3A, H3B | H3A tested-positive, H3B tested-null | `docs/BLEND.md` |
| `gates_study.py` | H4G, H4P, H4C | exploratory (no verdict) | `docs/GATES.md` |
| `sharp_book_probe.py` | H5 | tested-null | `docs/SHARP_BOOKS.md` |
| `censoring_study.py` | R05 | tested-null | `docs/CENSORING_STUDY.md` |
| `weather_gate.py` | R06 | rejected | `docs/WEATHER.md` |
| `residual_gate.py` (shim over `beatvegas.backtest.reporting`) | R03 | tested-null | its recorded 2025 numbers in the R03 row |
| `level_anchor_gate.py` | R04, H-LEVEL | R04 rejected, H-LEVEL tested-null | `docs/LEVEL_ANCHOR.md`, `docs/MODEL_LEVEL_2026.md` |
| `intercept_gate.py` | H-INTERCEPT | tested-null | `docs/MODEL_LEVEL_2026.md` |
| `inseason_gate.py` | H-INSEASON | tested-null | `docs/MODEL_LEVEL_2026.md` |
| `challenger_position.py` | H-INSEASON-P | superseded (withdrawn before a first pick) | `docs/INSEASON_PAPER.md` |
| `neggap_position.py` | H-NEGGAP-P | superseded (retired 2026-10-08) | `docs/NEGGAP_PAPER.md` |
| `neggap_level_study.py` | H-NEGGAP-L | superseded | `docs/TWO_SIDED.md` |
| `fg_position.py` | H-FG-P | superseded (replaced by H-ARM-FGU) | `docs/FG_MARKET.md` |
| `stopping_rule_position.py` | H-STOP, H-STOP-2 | superseded (H-STOP-2 closed inconclusive) | `docs/STOPPING_RULE.md` |
| `margin_backtest.py` | H-MARGIN | exploratory (closed null, Pick'em dropped) | `docs/MARGIN.md` |
| `model_fix_study.py` | H-MODEL-FIX | tested-null (NOT MET 2026-10-10) | `docs/MODEL_FIX.md` |
| `literature_look.py` | H-LIT-ARSCOTT, H-LIT-TV, H-LIT-BENNETT, H-LIT-COX | all tested-null | `docs/LITERATURE.md` |
| `weather_history_look.py` | H-WX-HIST | exploratory | `docs/program/REVIEW_2026-10.md` |
| `wepa_weekly_extract.py` | H-WEPA-F (arm R) | tested-null | `docs/WEPA_F.md` |
| `harness_report.py` | the runs behind H-WEPA-F, H-FG-U-R, H-FG-O-R, H-HIST, H-ELO-F | tested-null / tested-positive per row | `docs/HARNESS.md` and each row's doc |
| `publish_shortlist.py` | H-1H-SHORTLIST | rejected (stopped 2026-10-16) | `docs/HISTORY.md` |
| `build_shortlist_reference.py` | H-1H-SHORTLIST (reference freeze from H-1H-FACTORS) | rejected | `docs/HISTORY.md` |
| `bv_adjust.py` | none (a display-only nudge tool) | retired with the offline backtest engine, v2.0 | `docs/HISTORY.md` |
| `line_study.py` | none (the old Line Study CLI) | research-only since roadmap v2.0 | `README.md` (Line Study) |
| `model_artifacts.py` | none (read-only look at `model_artifacts`) | a lookup, no result | `beatvegas/model/artifacts.py` |
| `probe_hr_keys.py` | none (probe) | `hardrockbet` vs `hardrockbet_fl` | `docs/HISTORY.md` |
| `probe_alt_totals_h1.py` | none (programme 4.4 probe) | one by-hand run | `docs/PRICING_RESEARCH.md`, `docs/HISTORY.md` |

Two scripts import each other: `inseason_gate.py` and `intercept_gate.py` take
`load_closes` from `level_anchor_gate.py` (as `scripts.archive.level_anchor_gate`).
