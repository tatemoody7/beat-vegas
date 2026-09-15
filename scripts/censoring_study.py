#!/usr/bin/env python
"""Does censoring leave information the PRICE has not already absorbed?

A REPORT, NOT A BUILD. It exists to decide whether the two-team probabilistic
engine is worth multiple days, and it is allowed to say no. See
beatvegas/backtest/censoring.py for what each test can and cannot support, and
docs/CENSORING_STUDY.md for the first run.

    python scripts/censoring_study.py --out reports/censoring

Writes <out>_<UTC>.md and .json, appends the markdown to $GITHUB_STEP_SUMMARY
when set, and exits 0 whatever the numbers say. Reads Neon; writes nothing.
Spends no CFBD and no Odds API calls -- every input is already captured.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any, Dict, Optional, Sequence

import pandas as pd
from sqlalchemy import text

from beatvegas.backtest import censoring as C
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.lines import REAL_1H_CLOSE_WINDOW_H

HIST_SCOPE = "hist_2023_25"


def load_frame(scope: str = HIST_SCOPE) -> pd.DataFrame:
    """The real-close cut, joined to per-team 1H points and each book's closing
    quote. The close window matches lines.REAL_1H_CLOSE_WINDOW_H so this study
    and the post-mortem mean the same thing by "the close"."""
    with session_scope() as s:
        base = pd.DataFrame(
            s.execute(
                text(
                    """
                select p.game_id, p.season, p.week, p.line_real, p.outcome_real,
                       p.fh, p.spread, p.spread_abs, p.full_game_total,
                       g.home_first_half_points as home_fh,
                       g.away_first_half_points as away_fh
                from postmortem_games p
                join games g on g.id = p.game_id
                where p.scope = :scope and p.line_real is not null
                """
                ),
                {"scope": scope},
            )
            .mappings()
            .all()
        )
        quotes = pd.DataFrame(
            s.execute(
                text(
                    """
                select distinct on (o.game_id, o.book)
                       o.game_id, o.book, o.over_price, o.under_price
                from odds_snapshots o
                join games g on g.id = o.game_id
                join postmortem_games p
                  on p.game_id = o.game_id and p.scope = :scope
                where o.market = '1H_total'
                  and p.line_real is not null
                  and o.captured_at <= g.start_date
                  and g.start_date - o.captured_at <= make_interval(hours => :win)
                  and o.over_price is not null and o.under_price is not null
                order by o.game_id, o.book, o.captured_at desc
                """
                ),
                {"scope": scope, "win": int(REAL_1H_CLOSE_WINDOW_H)},
            )
            .mappings()
            .all()
        )
    for c in ("line_real", "fh", "spread", "spread_abs", "full_game_total", "home_fh", "away_fh"):
        base[c] = pd.to_numeric(base[c], errors="coerce")
    fair = C.closing_fair_under(quotes.to_dict("records"))
    base["fair_under"] = base["game_id"].map(fair)
    return base


def render_markdown(r: Dict[str, Any]) -> str:
    g, v = r["gate"], r["verdict"]
    pa = r["push_audit"]
    L = [
        "# Censoring study — does the price already absorb it?",
        "",
        f"Scope `{r['scope']}` · **{r['n_games']} games** with a real captured 1H close.",
        "",
        f"## Verdict: {'**BUILD**' if v['build'] else '**DO NOT BUILD**'}",
        "",
    ]
    for why in v["reasons"] or ["all three criteria met"]:
        L.append(f"- {why}")
    L += [
        "",
        f"_{v['rule']}_",
        "",
        "## Pushes (run first — a de-vigged price carries no push mass)",
        "",
        "| line type | n | pushes | push rate |",
        "|---|---|---|---|",
    ]
    for row in pa["by_line_type"]:
        L.append(f"| {row['line_type']} | {row['n']} | {row['pushes']} | {row['push_pct']:.2f}% |")
    L += [
        "",
        f"Under rate **{pa['under_pct_all']:.2f}% counting pushes** against "
        f"**{pa['under_pct_decided']:.2f}% among decided games** — ignoring this shifts every "
        f"comparison by {pa['bias_pp_if_ignored']:+.2f} pp. Everything below conditions on non-push.",
        "",
        "## Test 2 — THE GATE: does spread add anything to the book's own probability?",
        "",
        f"- market mean P(under) **{100 * g['market_mean_p']:.2f}%** vs realized "
        f"**{100 * g['under_rate']:.2f}%** (gap {100 * g['calibration_gap']:+.2f} pp)",
        f"- Brier: market **{g['brier_market']:.4f}**, a flat coin flip {g['brier_coinflip']:.4f}",
        f"- **spread coefficient {g['spread_coef']:+.5f} per point**, bootstrap 95% CI "
        f"[{g['spread_ci'][0]:+.5f}, {g['spread_ci'][1]:+.5f}] "
        f"({g['n_boot']} resamples) — excludes zero: **{g['spread_excludes_zero']}**",
        f"- market level unbiased: **{g['market_level_unbiased']}** "
        f"(intercept {g['intercept']:+.4f} CI [{g['intercept_ci'][0]:+.4f}, {g['intercept_ci'][1]:+.4f}])",
        f"- free-coefficient variant: market-logit **{g['free_market_logit_coef']:+.4f}** "
        f"(1.0 = calibrated), spread {g['free_spread_coef']:+.5f}",
        "",
        f"**Economic size.** Taken at face value the coefficient is worth "
        f"**{g['swing_pp_7_to_28']:+.2f} pp** of P(under) across the entire 7-to-28 spread range, "
        f"against a **{g['vig_hurdle_pp']} pp** vig hurdle at -110. Clears it: "
        f"**{g['clears_vig']}**.",
        "",
        "### Per season — is the coefficient even the same sign?",
        "",
        "| season | n | spread coef | realized | implied |",
        "|---|---|---|---|---|",
    ]
    for s in r["per_season"]:
        L.append(
            f"| {s['season']} | {s['n']} | {s['spread_coef']:+.5f} | "
            f"{100 * s['under_rate']:.1f}% | {100 * s['market_mean_p']:.1f}% |"
        )
    wf = r["walk_forward"]
    if wf.get("evaluable"):
        L += [
            "",
            f"### Walk-forward — fit on everything before {wf['test_season']}, score it blind",
            "",
            f"- trained n={wf['n_train']}, tested n={wf['n_test']}, spread coef {wf['spread_coef']:+.5f}",
            f"- Brier: market **{wf['brier_market']:.5f}** vs with-spread **{wf['brier_with_spread']:.5f}** "
            f"(delta {wf['brier_delta']:+.5f})",
            f"- log-loss: market **{wf['log_loss_market']:.5f}** vs with-spread "
            f"**{wf['log_loss_with_spread']:.5f}**",
        ]
        ci = wf.get("brier_delta_ci") or {}
        if ci.get("delta") is not None:
            L.append(
                f"- paired bootstrap on that delta ({ci['n_boot']} resamples): "
                f"**{ci['delta']:+.5f}** CI [{ci['lo']:+.5f}, {ci['hi']:+.5f}] — "
                f"excludes zero: **{ci['excludes_zero']}**"
            )
        cal = wf.get("calibration_market") or {}
        if cal:
            L += [
                "",
                "#### Is the market's price actually CENTRED?",
                "",
                "A Brier near 0.25 does not answer this. A constant 0.50 forecast scores "
                "exactly 0.25 on any binary sample whatever the base rate, and Brier "
                "decomposes as reliability - resolution + uncertainty, where uncertainty "
                "alone is p(1-p) — about 0.2500 at this Under rate. So 0.25 says the "
                "probabilities sit near a half with little resolution. These say whether "
                "they are centred:",
                "",
                f"- mean implied **{100 * cal['mean_predicted']:.2f}%** vs realized "
                f"**{100 * cal['mean_realized']:.2f}%** — bias **{cal['bias_pp']:+.2f} pp** "
                f"(calibration-in-the-large, n={cal['n']})",
                f"- calibration intercept **{cal['intercept']:+.4f}**, slope "
                f"**{cal['slope']:.4f}** (0 and 1 = calibrated; slope < 1 = over-confident)",
            ]
        rel = wf.get("reliability_market") or []
        if rel:
            L += [
                "",
                "| predicted | realized | n | Wilson 95% |",
                "|---|---|---|---|",
            ]
            for b in rel:
                lo = f"{100 * b['lo']:.1f}%" if b["lo"] is not None else "—"
                hi = f"{100 * b['hi']:.1f}%" if b["hi"] is not None else "—"
                L.append(
                    f"| {100 * b['predicted']:.1f}% | {100 * b['realized']:.1f}% | "
                    f"{b['n']} | {lo}–{hi} |"
                )
            L.append("")
            L.append(
                "Quantile bins, not equal-width: these probabilities cluster hard around "
                "0.50, so equal-width cutting leaves most bins empty and resolves nothing "
                "in the only region that has data."
            )
    L += [
        "",
        "### Realized minus implied, by spread bucket",
        "",
        "| bucket | n | realized | implied | diff | Wilson 95% |",
        "|---|---|---|---|---|---|",
    ]
    for b in r["realized_vs_implied"]:
        L.append(
            f"| {b['bucket']} | {b['n']} | {b['realized_pct']:.1f}% | {b['implied_pct']:.1f}% | "
            f"{b['diff_pp']:+.1f} pp | {b['lo_pct']:.1f}–{b['hi_pct']:.1f}% |"
        )
    L += [
        "",
        "## Test 1 — mechanism diagnostic (NOT a market test)",
        "",
        "This cannot show the market is wrong. It says whether a zero-mass component",
        "would be structurally worth having, if anything is ever built.",
        "",
        "| bucket | n | dog shutout | (Wilson) | fav shutout | dog mean | fav mean |",
        "|---|---|---|---|---|---|---|",
    ]
    for b in r["zero_mass"]:
        L.append(
            f"| {b['bucket']} | {b['n']} | **{b['dog_shutout_pct']:.1f}%** | "
            f"{b['dog_shutout_lo']:.1f}–{b['dog_shutout_hi']:.1f}% | {b['fav_shutout_pct']:.1f}% | "
            f"{b['dog_mean']:.1f} | {b['fav_mean']:.1f} |"
        )
    L += ["", "**Underdog first-half score support** (why any future model must be discrete):", ""]
    for s in r["score_support"]:
        L.append(f"- {s['points']:>2} points — {s['pct']:.1f}% of games")
    L += ["", f"_generated {r['generated_at']}_"]
    return "\n".join(L) + "\n"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--scope", default=HIST_SCOPE)
    p.add_argument("--out", default="reports/censoring")
    p.add_argument("--test-season", type=int, default=2025)
    # 400 is enough to look at; a CI that gets QUOTED in percentage points needs
    # more than that, and the whole run is seconds either way.
    p.add_argument("--n-boot", type=int, default=2000)
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try_init_db()
    df = load_frame(args.scope)

    report: Dict[str, Any] = {
        "kind": "censoring_study",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "scope": args.scope,
        "n_games": int(len(df)),
        "n_with_fair": int(df["fair_under"].notna().sum()),
        "push_audit": C.push_audit(df),
        "gate": C.spread_residual(df, n_boot=args.n_boot),
        "per_season": C.per_season(df),
        "walk_forward": C.walk_forward(df, args.test_season, n_boot=args.n_boot),
        "realized_vs_implied": C.realized_vs_implied(df),
        "zero_mass": C.zero_mass_by_bucket(df),
        "score_support": C.score_support(df),
    }
    report["verdict"] = C.verdict(report["gate"], report["per_season"], report["walk_forward"])

    from scripts.residual_gate import append_step_summary, report_paths

    md_path, json_path, _csv = report_paths(args.out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md = render_markdown(report)
    md_path.write_text(md)
    json_path.write_text(json.dumps(report, indent=2, default=str))
    append_step_summary(md)
    print(md)
    print(f"wrote {md_path.name}, {json_path.name}")
    print("VERDICT: BUILD" if report["verdict"]["build"] else "VERDICT: DO NOT BUILD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
