"""The prose must agree with the code about anything that decides money.

`test_gate_parity.py` stops Python and TypeScript disagreeing about the betting
gates. This extends the same idea one layer out, to the documents, because the
documents drifted worse than the code ever did.

Found 2026-09-14: `docs/BETTING_POLICY.md` stated that a bet requires "both teams
have played 2+ games; weeks 1-2 never qualify by design", while
`MIN_GAMES_FOR_MODEL` had been 0 since 2026-09-08 and nothing enforced it -- so
a week-1 game could reach BET. The document describing the money path was wrong
about the money path, which is the worst possible place for stale prose. The same
file also routed bets through a deleted Bet Slip, described scheduled texts that
had been retired, and contradicted itself about exchanges 140 lines apart.

A doc claim that contradicts a constant should fail CI, exactly the way a
TS/Python mismatch does.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from beatvegas import picks
from beatvegas.model import score

DOCS = Path(__file__).resolve().parent.parent / "docs"
POLICY = DOCS / "BETTING_POLICY.md"
GLOSSARY = DOCS / "GLOSSARY.md"
HEALTH_DOC = DOCS / "HEALTH.md"
WEB_LIB = DOCS.parent / "web" / "lib"


def _text(p: Path) -> str:
    if not p.exists():  # pragma: no cover - the docs are checked in
        pytest.skip(f"{p.name} not present in this checkout")
    return p.read_text()


# --------------------------------------------------------------------------- #
# docs/HEALTH.md is prose plus a block generated from beatvegas/health.py
# --------------------------------------------------------------------------- #
def test_health_doc_block_is_the_rendered_contracts():
    """`python -m beatvegas.health --render-md docs/HEALTH.md` regenerates the
    block between the markers; a contract edited without re-rendering fails here."""
    from beatvegas import health

    body = _text(HEALTH_DOC)
    start = body.index(health.CONTRACTS_BEGIN)
    end = body.index(health.CONTRACTS_END) + len(health.CONTRACTS_END)
    assert body[start:end] + "\n" == health.render_contracts()
    # The prose names every job's runbook (the board links docs/HEALTH.md#<job>).
    for job in health.CONTRACTS:
        assert f"When {job} is degraded" in body, job


def test_the_stale_hours_the_health_check_uses_are_the_boards():
    """grade.finals_landed is the board's stale-results predicate
    (web/lib/boardHealth.ts getGradeHealth); the two thresholds must agree or
    the banner and the verdict disagree about the same fact."""
    from beatvegas import health

    web = _text(WEB_LIB / "boardHealth.ts")
    m = re.search(r"export const STALE_AFTER_HOURS = (\d+);", web)
    assert m, "boardHealth.ts no longer declares STALE_AFTER_HOURS"
    assert int(m.group(1)) == health.STALE_AFTER_HOURS


def test_the_close_coverage_floor_the_health_check_uses_is_the_boards():
    """lines_watch.close_window_coverage and the board's `close_coverage` warning
    judge the same share against the same floor (2026-09-28)."""
    from beatvegas import health

    web = _text(WEB_LIB / "boardHealth.ts")
    m = re.search(r"export const CLOSE_COVERAGE_MIN = ([0-9.]+);", web)
    assert m, "boardHealth.ts no longer declares CLOSE_COVERAGE_MIN"
    assert float(m.group(1)) == health.CLOSE_COVERAGE_MIN


# --------------------------------------------------------------------------- #
# Numbers the docs quote
# --------------------------------------------------------------------------- #
def test_the_gap_rule_in_the_docs_is_the_one_in_the_code():
    """H-PCT (2026-09-22): the bar is the slate's top-PCT_SHARE by gap; the old
    constant is only the empty-slate fallback. Both docs must say the share the
    code uses and the fallback the code uses -- and neither may still present
    the constant as THE rule."""
    share_pct = int(round(score.PCT_SHARE * 100))
    for doc in (POLICY, GLOSSARY):
        body = _text(doc)
        shares = {int(m) for m in re.findall(r"top ([0-9]+)%", body)}
        assert share_pct in shares, f"{doc.name} should state the top-{share_pct}% share"
        fallback = {
            float(m) for m in re.findall(r"bv_gap ≥ ([0-9.]+)|is ([0-9.]+)\.", body) for m in m if m
        }
        assert score.BET_GAP_PTS in fallback, (
            f"{doc.name} should name the fallback bar {score.BET_GAP_PTS}"
        )
        assert "≥ 1.75 points above" not in body, (
            f"{doc.name} still presents the constant as the rule"
        )


def test_the_weekly_cap_in_the_docs_is_the_one_in_the_code():
    body = _text(POLICY)
    quoted = {int(m) for m in re.findall(r"capped at (\d+) real-money bets", body)}
    assert quoted == {score.WEEKLY_BET_CAP}


def test_the_real_money_games_minimum_matches():
    body = _text(POLICY)
    quoted = {int(m) for m in re.findall(r"MIN_GAMES_FOR_REAL_MONEY = (\d+)", body)}
    assert quoted == {score.MIN_GAMES_FOR_REAL_MONEY}


def test_the_model_minimum_matches_and_is_not_confused_with_the_money_one():
    body = _text(POLICY)
    quoted = {int(m) for m in re.findall(r"`MIN_GAMES_FOR_MODEL` has been \*\*(\d+)\*\*", body)}
    assert quoted == {score.MIN_GAMES_FOR_MODEL}
    # The two are different rules and the doc has to keep them apart: one is a
    # modelling capability, the other a policy about money.
    assert score.MIN_GAMES_FOR_MODEL != score.MIN_GAMES_FOR_REAL_MONEY
    assert "MIN_GAMES_FOR_REAL_MONEY" in body


def test_the_paper_stake_the_docs_quote_is_the_one_in_the_code():
    """Paper picks stake a flat unit so their units/ROI stay comparable."""
    quoted = {int(m) for m in re.findall(r"`is_paper`, (\d+)-unit stake", _text(POLICY))}
    assert quoted == {int(picks.PAPER_STAKE)}


# --------------------------------------------------------------------------- #
# Claims that were true once and are not any more
# --------------------------------------------------------------------------- #
def test_the_docs_do_not_claim_a_two_game_minimum_for_a_MODEL_read():
    """The exact sentence that was wrong. The model reads week 1; only money waits."""
    body = _text(POLICY)
    assert "weeks 1–2 never\n   qualify by design" not in body
    assert "weeks 1-2 never qualify by design" not in body


def test_the_docs_do_not_route_bets_through_the_deleted_bet_slip():
    body = _text(POLICY)
    # Naming it as DELETED is fine and useful; describing it as the live path is not.
    for claim in ("via\n  the Bet Slip", "bets off the Bet Slip", "in the BET list or the Bet"):
        assert claim not in body, f"BETTING_POLICY still routes bets through: {claim!r}"


def test_the_docs_do_not_promise_scheduled_texts_or_routines():
    for doc in (POLICY, GLOSSARY):
        body = _text(doc)
        for claim in ("text the BET list", "texts Tate", "the Saturday text", "Ops routine"):
            assert claim not in body, f"{doc.name} still promises a retired routine: {claim!r}"


def test_the_glossary_does_not_call_the_flat_proxy_current():
    body = _text(GLOSSARY)
    assert "estimate one as **0.52 × the full-game total**" not in body
    # and it must name the step proxy that replaced it
    assert "0.4975" in body and "0.5375" in body


def test_the_glossary_no_longer_defines_the_under_score():
    """The 0-100 classifier score was retired on 2026-10-04
    (docs/CLASSIFIER_RETIREMENT.md). The entry that used to explain why "50 =
    breakeven" was incoherent is gone with it; nothing may describe the score as
    a live number again."""
    body = _text(GLOSSARY)
    assert "**Under Score" not in body
    assert "rescaled probability" not in body
    assert "50 = breakeven-neutral" not in body


def test_the_glossary_does_not_call_data_sources_free():
    body = _text(GLOSSARY)
    assert "## Data sources (all free)" not in body
    assert "free tier (500/mo)" not in body


def test_the_glossary_does_not_say_prediction_markets_have_no_vig():
    body = _text(GLOSSARY)
    assert "prices carry ~no vig" not in body


def test_neither_doc_claims_exchanges_sharpen_the_FIRST_HALF_price():
    """They feed the full-game context only: `us_ex` returns zero 1H bookmakers."""
    for doc in (POLICY, GLOSSARY):
        body = _text(doc)
        assert 'sharpen the "market fair price" Hard Rock' not in body
        assert "to sharpen the market fair price" not in body


def test_the_docs_do_not_claim_weather_helped():
    body = _text(GLOSSARY)
    assert "pace (tempo) + weather — the only inputs" not in body
    assert "open hypothesis" in body


def test_the_docs_do_not_claim_the_edge_is_real():
    """Something cannot be both real and unconfirmed."""
    body = _text(GLOSSARY)
    assert "the edge is real" not in body
    assert "does not currently have a confirmed" in body


def test_the_clv_direction_convention_is_stated_the_way_the_code_computes_it():
    """Stored CLV is closing - bet, so for an under NEGATIVE is favourable. The
    site reported this backwards for a week; the docs must not reintroduce it."""
    body = _text(GLOSSARY)
    assert re.search(r"negative is the\s*\n?\s*good direction", body, re.I)


# --------------------------------------------------------------------------- #
# docs/WHEN_TO_BET.md quotes the H6 rule's constants
# --------------------------------------------------------------------------- #
def test_when_to_bet_doc_quotes_the_pre_registered_constants():
    from beatvegas.backtest import when_to_bet as W

    body = _text(DOCS / "WHEN_TO_BET.md")
    assert W.CONFIRMATORY_DATE.isoformat() in body
    assert f"n ≥ {W.MIN_MATCHED}" in body
    assert f"alpha **{int(W.FAMILY_ALPHA * 100)}%**" in body
    assert "NOT YET EVALUABLE" in body


# --------------------------------------------------------------------------- #
# docs/BLEND.md quotes the frozen w and the H3B constants
# --------------------------------------------------------------------------- #
def test_blend_doc_quotes_the_frozen_w_and_the_bucket_rule():
    import json

    from beatvegas.backtest import blend as B

    body = _text(DOCS / "BLEND.md")
    frozen = json.loads((DOCS.parent / "data" / "blend.json").read_text())
    assert f"w = {frozen['w']:.2f}" in body and frozen["fitted_on"] == "2023-2025"
    assert f"n ≥ {B.MIN_BUCKET_N}" in body
    assert f"{int(B.FAMILY_ALPHA * 100)}%" in body
    assert "BLEND WINS AT CLOSE" in body and "NOT ADOPTED" in body


def test_nothing_reads_the_frozen_blend():
    """data/blend.json is a measurement. The only code that names it is its writer."""
    root = DOCS.parent
    offenders = []
    for folder in ("beatvegas", "scripts", "web/lib", "web/app"):
        for p in (root / folder).rglob("*"):
            if p.suffix in (".py", ".ts", ".tsx") and "blend.json" in p.read_text(errors="ignore"):
                if p.name not in ("blend.py", "blend_gate.py"):  # the writer and its CLI
                    offenders.append(str(p.relative_to(root)))
    assert offenders == [], offenders


# --------------------------------------------------------------------------- #
# docs/GATES.md quotes the H4 constants and stays exploratory
# --------------------------------------------------------------------------- #
def test_gates_doc_quotes_its_constants_and_makes_no_verdict():
    from beatvegas.backtest import gates as G

    body = _text(DOCS / "GATES.md")
    assert f"n ≥ {G.WILSON_MIN_N}" in body
    assert f"{G.FIXED_CEILING}" in body
    assert f"(n·ratio + {G.TRUST_K})/(n + {G.TRUST_K})" in body
    assert f"n = {G.TRUST_MIN_N}" in body
    assert "EXPLORATORY" in body
    assert "COSTLY**" not in body and "PROTECTIVE**" not in body


# --------------------------------------------------------------------------- #
# docs/SHARP_BOOKS.md quotes the probe's regions and budget
# --------------------------------------------------------------------------- #
def test_sharp_books_doc_quotes_the_probe_constants():
    from tests.conftest import _load_script

    P = _load_script("sharp_book_probe")
    body = _text(DOCS / "SHARP_BOOKS.md")
    assert ", ".join(P.DISCOVERY_REGIONS.split(",")) in body
    assert f"cap {P.parse_args([]).max_credits} credits" in body
    assert "no swap" in body.lower()


# --------------------------------------------------------------------------- #
# docs/STOPPING_RULE.md quotes the registered constants
# --------------------------------------------------------------------------- #
def test_stopping_rule_doc_quotes_the_registered_constants():
    from beatvegas.backtest import stopping as S

    r = S.REGISTERED
    b = S.sprt_bounds(r["alpha_clock"], 1 - r["power"])
    body = _text(DOCS / "STOPPING_RULE.md")
    assert r["registered_on"] in body and "SPRT" in body
    assert f"{100 * r['alpha_total']:.0f}%, {100 * r['alpha_clock']:.1f}% per clock" in body
    assert f"+{r['mu1']['profit']:.4f} u/bet" in body and f"+{r['mu1']['clv']:.2f} pts/bet" in body
    assert f"A = ln((1−β)/α) = {b['A']:.3f}" in body and f"B = ln(β/(1−α)) = {b['B']:.3f}" in body
    assert "2026 week 3" in body and "pauses real money" in body
    assert "no confidence band" in body


# --- The gap >= 1.75 real-close cohort, 2023-25 (2026-10-07). Two docs quoted it
# as 295 (RANKING_AND_TRUST) and 296 (POST_MORTEM): the post-mortem doc was a
# 2026-09-07 snapshot taken before later data repairs, and the run behind it is
# no longer stored. The cohort is now frozen as game ids, and both docs must
# quote its count, record and units.

COHORT = Path(__file__).resolve().parent / "fixtures" / "gap175_real_cohort_2023_25.json"


def _cohort() -> dict:
    import json

    c = json.loads(COHORT.read_text())
    assert c["n"] == len(c["game_ids"]) == len(set(c["game_ids"]))
    assert c["wins"] + c["losses"] + c["pushes"] == c["n"]
    return c


def test_ranking_and_trust_quotes_the_frozen_gap175_cohort():
    c = _cohort()
    body = _text(DOCS / "RANKING_AND_TRUST.md")
    head = f"**{c['n']} bets, {c['wins']}-{c['losses']}-{c['pushes']},"
    assert head in body, head
    assert f"| All weeks | {c['n']} | {c['wins']}-{c['losses']} |" in body
    assert f"{c['units']:+.2f} units" in body


def test_post_mortem_doc_quotes_the_frozen_gap175_cohort():
    c = _cohort()
    body = _text(DOCS / "POST_MORTEM.md")
    rows = re.findall(
        r"^\| Every gap ≥ 1\.75 \| all \| real[^|]* \| (\d+) \| (\d+)-(\d+)-(\d+)P \|", body, re.M
    )
    assert rows, "the hist headline row for gap >= 1.75 at real closes is missing"
    n, wins, losses, pushes = map(int, rows[0])
    assert (n, wins, losses, pushes) == (c["n"], c["wins"], c["losses"], c["pushes"])


# --------------------------------------------------------------------------- #
# The season's end (protocol p1.3, roadmap v2.6): one date everywhere
# --------------------------------------------------------------------------- #
def test_every_governing_doc_states_the_final_read_date():
    """Final-2026 plan D1/D4 (2026-10-18): paid capture ends after 2026-11-28 and the final
    read is 2026-11-30. The code holds the date once (protocol.FINAL_READ_DATE); the roadmap,
    the protocol, the registry, the review templates, the H6 doc and the brief must say the
    same, and H6's own constant must be that day."""
    from datetime import date

    from beatvegas import protocol as P
    from beatvegas.backtest import when_to_bet as W

    assert P.FINAL_READ_DATE == "2026-11-30"
    assert W.CONFIRMATORY_DATE == date.fromisoformat(P.FINAL_READ_DATE)
    root = DOCS.parent
    for rel in (
        "docs/ROADMAP_2026.md",
        "docs/PROTOCOL_2026.md",
        "docs/HYPOTHESES.md",
        "docs/WHEN_TO_BET.md",
        "docs/program/JANUARY_2027_REVIEW.md",
        "CLAUDE.md",
    ):
        body = _text(root / rel)
        assert P.FINAL_READ_DATE in body or "11-30" in body, rel
    roadmap = _text(root / "docs" / "ROADMAP_2026.md")
    assert "| v2.6 | 2026-10-18 |" in roadmap and "2026-11-28" in roadmap
    protocol = _text(root / "docs" / "PROTOCOL_2026.md")
    assert f"`{P.PROTOCOL_VERSION}`" in protocol and P.SEASON_LAST_KICKOFF[:10] in protocol
