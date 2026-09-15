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


def _text(p: Path) -> str:
    if not p.exists():  # pragma: no cover - the docs are checked in
        pytest.skip(f"{p.name} not present in this checkout")
    return p.read_text()


# --------------------------------------------------------------------------- #
# Numbers the docs quote
# --------------------------------------------------------------------------- #
def test_the_gap_threshold_in_the_docs_is_the_one_in_the_code():
    for doc in (POLICY, GLOSSARY):
        body = _text(doc)
        quoted = {
            float(m)
            for m in re.findall(r"bv_gap ≥ ([0-9.]+)|≥ ([0-9.]+) points above", body)
            for m in m
            if m
        }
        assert quoted, f"{doc.name} should state the gap threshold"
        assert quoted == {score.BET_GAP_PTS}, (
            f"{doc.name} quotes {quoted}, code says {score.BET_GAP_PTS}"
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


def test_the_glossary_does_not_call_under_score_a_probability():
    body = _text(GLOSSARY)
    assert "rescaled probability" not in body
    assert "50 = breakeven-neutral" not in body
    # -110 breakeven is 52.38%, which is why "50 = breakeven" was incoherent
    assert "52.38" in body


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
