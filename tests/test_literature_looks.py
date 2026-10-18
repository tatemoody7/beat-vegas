"""The literature looks (docs/HYPOTHESES.md H-LIT-ARSCOTT / H-LIT-TV / H-LIT-BENNETT,
Tate's calls of 2026-10-08; H-LIT-COX, 2026-10-11): the median close, Arscott's
censoring bias, the national-TV reading, Bennett's first game played, Cox's
last-three streak, the grading signs, the exact binomial, Holm with m = 6 fixed,
and the script end to end on a fake CFBD."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from beatvegas.backtest import literature as L
from beatvegas.registry import HarnessRefusal, find_row, parse_registry, require_runnable_row

ROOT = Path(__file__).resolve().parent.parent
FBS = {2019: {"A", "B", "C", "D", "E", "F"}, 2020: {"A", "B", "C", "D", "E", "F"}}


def _script():
    path = ROOT / "scripts" / "archive" / "literature_look.py"
    spec = importlib.util.spec_from_file_location("literature_look", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _game(gid, home, away, hp, ap, season=2019, week=1, date="2019-09-07T16:00:00.000Z", **kw):
    g = {
        "id": gid,
        "season": season,
        "week": week,
        "seasonType": "regular",
        "startDate": date,
        "homeTeam": home,
        "awayTeam": away,
        "homeConference": kw.pop("hc", "X"),
        "awayConference": kw.pop("ac", "Y"),
        "homePoints": hp,
        "awayPoints": ap,
        "completed": hp is not None,
    }
    g.update(kw)
    return g


def _lines(*pairs):
    """[(spread, overUnder), ...] -> CFBD provider rows."""
    return [{"provider": f"p{i}", "spread": s, "overUnder": t} for i, (s, t) in enumerate(pairs)]


# --- the line ---------------------------------------------------------------------


def test_median_close_odd_even_skips_missing():
    assert L.median_close(_lines((-7, 50), (-7.5, 51), (-8, None)), "spread") == (-7.5, 3)
    assert L.median_close(_lines((-7, 50), (-7.5, 51), (-8, None)), "overUnder") == (50.5, 2)
    assert L.median_close(_lines((None, None)), "spread") == (None, 0)
    assert L.median_close(None, "spread") == (None, 0)


# --- Arscott ----------------------------------------------------------------------


def test_censoring_bias_matches_the_hand_numbers_and_the_cut():
    # Total 50: a 28-point spread sits just under the cut, 29 just over (computed
    # 2026-10-08 from the paper's formula and sigmas).
    assert L.censoring_bias(50, -28) == pytest.approx(0.987, abs=0.001)
    assert L.censoring_bias(50, 29) == pytest.approx(1.072, abs=0.001)
    assert L.censoring_bias(50, -29) == L.censoring_bias(50, 29)  # sign-free
    assert L.censoring_bias(50, 0) is None  # no favourite (Tate 2026-10-08)
    # one team's closed form against E[max(X, 0)] - mu integrated numerically
    from scipy.integrate import quad
    from scipy.stats import norm

    for mu, sigma in ((11.0, 11.28), (3.0, 11.28), (38.0, 11.941), (-2.0, 11.28)):
        e_max = quad(lambda x, m=mu, s=sigma: x * norm.pdf(x, m, s), 0, mu + 12 * sigma)[0]
        assert L._team_bias(mu, sigma) == pytest.approx(e_max - mu, abs=1e-6)


def test_arscott_rows_filters_and_flags():
    games = [
        _game(1, "A", "B", 45, 7),  # graded, big spread -> qualifies
        _game(2, "C", "D", 21, 20),  # graded, small spread
        _game(3, "E", "F", None, None),  # not played
        _game(4, "A", "C", 30, 10),  # no provider
        _game(5, "B", "D", 24, 24),  # spread zero
        _game(6, "A", "FCS U", 70, 0),  # not FBS-vs-FBS: outside the universe
    ]
    lines = {
        1: _lines((-30, 50), (-30.5, 50)),
        2: _lines((-3, 55)),
        5: _lines((0, 48)),
        6: _lines((-45, 60)),
    }
    rows, drops = L.arscott_rows(games, lines, FBS)
    assert [r["game_id"] for r in rows] == [1, 2]
    assert drops == {"universe": 5, "not_played": 1, "no_provider": 1, "spread_zero": 1}
    big, small = rows
    assert big["qualifies"] and not small["qualifies"]
    assert big["spread"] == -30.25 and big["total"] == 50.0
    assert big["result"] == "win"  # 52 points over 50
    assert small["result"] == "loss"  # 41 under 55


# --- national TV ------------------------------------------------------------------


def test_national_outlets_are_exactly_the_five_on_tv():
    rows = [
        {"mediaType": "tv", "outlet": "ESPN2"},
        {"mediaType": "tv", "outlet": "abc"},
        {"mediaType": "web", "outlet": "ESPN"},
        {"mediaType": "tv", "outlet": " FOX "},
        {"mediaType": "tv", "outlet": "FS1"},
    ]
    assert L.national_outlets(rows) == ["ABC", "FOX"]
    assert L.national_outlets([{"mediaType": "tv", "outlet": "CBSSN"}]) == []
    assert L.national_outlets(None) == []


def test_tv_rows_groups_and_grades_the_under():
    games = [_game(1, "A", "B", 20, 10), _game(2, "C", "D", 40, 30), _game(3, "E", "F", 28, 20)]
    lines = {1: _lines((-3, 50)), 2: _lines((-3, 50)), 3: _lines((-1, 48))}
    media = {
        1: [{"mediaType": "tv", "outlet": "ABC"}, {"mediaType": "tv", "outlet": "ESPN2"}],
        2: [{"mediaType": "tv", "outlet": "ESPNU"}],
    }
    rows, drops = L.tv_rows(games, lines, media, FBS)
    assert drops == {"universe": 3}
    by = {r["game_id"]: r for r in rows}
    assert by[1]["group"] == "national" and by[1]["networks"] == "ABC"
    assert by[1]["result"] == "win"  # 30 under 50
    assert by[2]["group"] == "other" and by[2]["result"] == "loss"  # 70 over 50
    assert by[3]["group"] == "no_media" and by[3]["result"] == "push"  # 48 on 48


# --- Bennett ----------------------------------------------------------------------


def _poll(week, ranks, poll="AP Top 25", season_type="postseason"):
    return {
        "season": 2018,
        "seasonType": season_type,
        "week": week,
        "polls": [
            {"poll": "Coaches Poll", "ranks": [{"rank": 1, "school": "Z"}]},
            {"poll": poll, "ranks": [{"rank": r, "school": s} for r, s in ranks]},
        ],
    }


def test_final_top10_reads_the_last_postseason_ap_release_with_ties():
    weeks = [
        _poll(1, [(1, "OLD")]),
        _poll(2, [(1, "A"), (2, "B"), (10, "C"), (10, "D"), (11, "E")]),
        _poll(16, [(1, "REG")], season_type="regular"),
    ]
    assert L.final_top10(weeks) == {"A": 1, "B": 2, "C": 10, "D": 10}
    assert L.final_top10([_poll(1, [(1, "A")], poll="Coaches Poll")]) == {}
    assert L.final_top10([]) == {}


def test_first_game_played_skips_cancelled_and_counts_fcs_openers():
    games = [
        _game(1, "A", "B", None, None, date="2019-08-31T16:00:00.000Z"),  # cancelled
        _game(2, "A", "C", 30, 20, date="2019-09-07T16:00:00.000Z"),
        _game(3, "D", "FCS U", 50, 3, date="2019-08-31T16:00:00.000Z"),
        _game(4, "D", "E", 10, 7, date="2019-09-07T16:00:00.000Z"),
    ]
    first = L.first_games_played(games)
    assert first["A"]["id"] == 2  # the first game PLAYED (Tate 2026-10-08)
    assert first["D"]["id"] == 3  # any opponent, FCS included


def test_ats_result_sign_hand_worked():
    # Home -7 wins by 10: home covers by 3.
    assert L.ats_result(31, 21, -7.0, bet_home=True) == "win"
    assert L.ats_result(31, 21, -7.0, bet_home=False) == "loss"
    # Home +3 loses by 3: a push.
    assert L.ats_result(17, 20, 3.0, bet_home=False) == "push"


def test_bennett_rows_fades_and_drops():
    games = [
        _game(1, "A", "B", 24, 21, date="2019-08-31T16:00:00.000Z"),  # A top 10 at home, -10
        _game(2, "FCS U", "C", 0, 60, date="2019-08-31T16:00:00.000Z"),  # C opens vs FCS
        _game(3, "D", "E", 30, 27, date="2019-08-31T16:00:00.000Z"),  # both top 10
        _game(4, "F", "B", 40, 0, date="2019-09-07T16:00:00.000Z"),  # F, no provider
    ]
    lines = {1: _lines((-10, 55)), 3: _lines((-2, 50))}
    top10 = {"A": 3, "C": 5, "D": 1, "E": 9, "F": 10, "GHOST": 7}
    detail = []
    rows, drops = L.bennett_rows(games, lines, top10, FBS, detail=detail)
    assert len(rows) == 1
    r = rows[0]
    assert (r["faded"], r["opponent"], r["faded_home"]) == ("A", "B", True)
    # Fade A = bet B +10; A won by 3, so B covers.
    assert r["result"] == "win"
    assert drops == {
        "universe": 6,
        "not_fbs_vs_fbs": 1,
        "both_top10": 2,
        "no_provider": 1,
        "no_game_played": 1,
    }
    assert ("GHOST", "no_game_played") in detail and ("C", "not_fbs_vs_fbs") in detail


# --- Cox ---------------------------------------------------------------------------


def _meeting(date, home, away, hs, as_):
    winner = None if hs == as_ else (home if hs > as_ else away)
    return {
        "season": int(date[:4]),
        "seasonType": "regular",
        "date": date,
        "homeTeam": home,
        "awayTeam": away,
        "homeScore": hs,
        "awayScore": as_,
        "winner": winner,
    }


PAIRS = {frozenset({"A", "B"}), frozenset({"C", "D"}), frozenset({"E", "F"})}
SERIES = {
    # A won the last three (a tie in between is skipped, not a break); older loss ignored.
    frozenset({"A", "B"}): [
        _meeting("2014-11-01T20:00:00.000Z", "B", "A", 30, 10),
        _meeting("2015-11-01T20:00:00.000Z", "A", "B", 21, 14),
        _meeting("2016-11-01T20:00:00.000Z", "B", "A", 17, 17),
        _meeting("2017-11-01T20:00:00.000Z", "B", "A", 7, 24),
        _meeting("2018-01-01T20:00:00.000Z", "A", "B", 35, 31),  # a bowl counts
        _meeting("2019-12-01T20:00:00.000Z", "A", "B", 99, 0),  # AFTER the 2019 game: ignored
    ],
    # C and D split the last three.
    frozenset({"C", "D"}): [
        _meeting("2016-11-01T20:00:00.000Z", "C", "D", 20, 10),
        _meeting("2017-11-01T20:00:00.000Z", "D", "C", 20, 10),
        _meeting("2018-11-01T20:00:00.000Z", "C", "D", 20, 10),
    ],
    # E and F have met twice.
    frozenset({"E", "F"}): [
        _meeting("2017-11-01T20:00:00.000Z", "E", "F", 20, 10),
        _meeting("2018-11-01T20:00:00.000Z", "E", "F", 20, 10),
    ],
}


def test_prior_meetings_and_streak_winner_skip_ties_and_later_games():
    prior = L.prior_meetings(SERIES[frozenset({"A", "B"})], "2019-09-07T16:00:00.000Z")
    assert [m["date"][:4] for m in prior] == ["2018", "2017", "2016", "2015", "2014"]
    assert L.streak_winner(prior) == ("A", 4)  # the tie is skipped; 2014's loss is 4th
    assert L.streak_winner(prior[:3]) == (None, 2)  # A, A and a tie: only two decided
    assert L.streak_winner(L.prior_meetings(SERIES[frozenset({"C", "D"})], "2019-09-07")) == (
        None,
        3,
    )
    assert L.streak_winner(L.prior_meetings(SERIES[frozenset({"E", "F"})], "2019-09-07")) == (
        None,
        2,
    )
    assert L.streak_winner([]) == (None, 0)
    # A meeting without a score (never played) is not a meeting.
    unplayed = [
        {
            "date": "2018-11-01",
            "homeTeam": "A",
            "awayTeam": "B",
            "homeScore": None,
            "awayScore": None,
        }
    ]
    assert L.prior_meetings(unplayed, "2019-01-01") == []


def test_conference_pairing():
    assert L.conference_pairing("SEC", "Big Ten") == "P5-P5"
    assert L.conference_pairing("SEC", "Sun Belt") == "P5-G5"
    assert L.conference_pairing("MAC", None) == "G5-G5"


def test_cox_rows_tests_the_streak_favourite_and_drops():
    games = [
        _game(
            1, "A", "B", 31, 10, hc="SEC", ac="SEC"
        ),  # A -7 favourite, won last 3 -> qualifies, covers
        _game(2, "D", "C", 20, 30, hc="MAC", ac="MAC"),  # split series: a row, not qualifying
        _game(3, "E", "F", 20, 10),  # two prior meetings: dropped
        _game(4, "A", "C", 40, 0),  # not a trophy pair: outside the universe
        _game(5, "B", "A", None, None, date="2019-11-30T20:00:00.000Z"),  # not played
        _game(6, "A", "B", 20, 20, date="2019-11-15T20:00:00.000Z"),  # pick'em
        _game(7, "C", "D", 20, 20, date="2019-11-20T20:00:00.000Z"),  # no provider
    ]
    lines = {
        1: _lines((-7, 50), (-6.5, 51)),
        2: _lines((3, 44)),  # D +3 at home: C the favourite, C won by 10 -> covers
        3: _lines((-10, 40)),
        4: _lines((-30, 50)),
        6: _lines((0, 50)),
    }
    rows, drops = L.cox_rows(games, lines, PAIRS, SERIES, FBS)
    assert drops == {
        "universe": 6,
        "not_played": 1,
        "pickem": 1,
        "no_provider": 1,
        "lt3_meetings": 1,
    }
    assert [r["game_id"] for r in rows] == [1, 2]
    a, c = rows
    assert (a["favourite"], a["favourite_home"], a["streak_team"], a["qualifies"]) == (
        "A",
        True,
        "A",
        True,
    )
    assert a["spread"] == -6.75 and a["result"] == "win" and a["pairing"] == "P5-P5"
    assert a["underdog_result"] == "loss" and a["prior_decided"] == 4
    assert (c["favourite"], c["favourite_home"], c["streak_team"], c["qualifies"]) == (
        "C",
        False,
        "",
        False,
    )
    assert c["result"] == "win" and c["underdog_result"] == "loss" and c["pairing"] == "G5-G5"


# --- the test and the family -------------------------------------------------------


def test_record_units_and_exact_binomial():
    rec = L.record(["win"] * 45 + ["loss"] * 25 + ["push"] * 2)
    assert (rec["wins"], rec["losses"], rec["pushes"], rec["n"]) == (45, 25, 2, 70)
    assert rec["p"] == pytest.approx(0.0297, abs=0.0002)  # scipy binomtest, 2026-10-08
    assert rec["units"] == pytest.approx(45 * (100 / 110) - 25, abs=0.01)
    assert L.record([])["p"] is None


def test_holm_family_fixes_m_at_six_and_counts_unrun_looks_as_one():
    alone = L.holm_family({L.TV: 0.006})[L.TV]
    assert alone["holm_p"] == pytest.approx(0.036)
    assert alone["verdict"] == "PASS"
    miss = L.holm_family({L.TV: 0.02})[L.TV]
    assert miss["holm_p"] == pytest.approx(0.12)
    assert miss["verdict"].startswith("not met so far")
    # A raw p at or above 5% can never pass: Holm's loosest step tests at 5% itself.
    assert L.holm_family({L.TV: 0.513})[L.TV]["verdict"] == "NOT MET"
    assert L.holm_family({L.TV: 0.05})[L.TV]["verdict"] == "NOT MET"
    # A second small p lowers the first one's threshold (Holm step-down).
    two = L.holm_family({L.ARSCOTT: 0.001, L.TV: 0.009})
    assert two[L.ARSCOTT]["holm_p"] == pytest.approx(0.006)
    assert two[L.TV]["holm_p"] == pytest.approx(0.045)
    assert two[L.TV]["verdict"] == "PASS"
    full = L.holm_family({f"L{i}": 0.5 for i in range(6)})
    assert all(v["verdict"] == "NOT MET" for v in full.values())
    with pytest.raises(ValueError):
        L.holm_family({f"L{i}": 0.5 for i in range(7)})


def test_decided_looks_are_refused_and_cox_is_runnable(capsys):
    """The three looks of 2026-10-09 are decided: the registry gate refuses each,
    so the script exits 2 before any CFBD call. H-LIT-COX (registered 2026-10-11)
    is pre-registered and runnable once."""
    mod = _script()
    for rid in (L.ARSCOTT, L.TV, L.BENNETT):
        assert find_row(parse_registry(), rid).status == "tested-null"
        with pytest.raises(HarnessRefusal):
            require_runnable_row(rid)
        assert mod.main(["--row", rid]) == 2
    assert "REFUSED" in capsys.readouterr().err
    cox = find_row(parse_registry(), L.COX)
    assert cox.status in {"pre-registered", "tested-null", "tested-positive"}
    if cox.status == "pre-registered":
        assert require_runnable_row(L.COX).criterion.startswith("PASS = ")


# --- the script --------------------------------------------------------------------


class _FakeCFBD:
    calls_remaining = 1234

    def __init__(self):
        self.calls = []

    def games(self, year, season_type="regular"):
        self.calls.append(("games", year, season_type))
        return [
            _game(10 * year + 1, "A", "B", 45, 7, season=year),
            _game(10 * year + 2, "C", "D", 20, 10, season=year),
        ]

    def lines(self, year, season_type="regular"):
        self.calls.append(("lines", year, season_type))
        return [
            {"id": 10 * year + 1, "lines": _lines((-30, 50))},
            {"id": 10 * year + 2, "lines": _lines((-3, 50))},
        ]

    def game_media(self, year, season_type="regular"):
        self.calls.append(("media", year, season_type))
        return [{"id": 10 * year + 2, "mediaType": "tv", "outlet": "CBS"}]

    def rankings(self, year, season_type="regular"):
        self.calls.append(("rankings", year, season_type))
        return [_poll(1, [(2, "A")])]

    def matchup(self, team1, team2, min_year=None):
        self.calls.append(("matchup", team1, team2))
        return {"team1": team1, "team2": team2, "games": SERIES.get(frozenset({team1, team2}), [])}


@pytest.mark.parametrize("row_id", sorted(L.LOOKS))
def test_run_look_end_to_end_writes_md_json_csv(tmp_path, monkeypatch, row_id):
    mod = _script()
    monkeypatch.setattr(L, "LOOKS", {**L.LOOKS, row_id: (2019, 2020)})
    client = _FakeCFBD()
    res = mod.run_look(row_id, client, FBS, pairs=PAIRS if row_id == L.COX else None)
    if row_id == L.COX:
        assert ("matchup", "A", "B") in client.calls and len(
            [c for c in client.calls if c[0] == "matchup"]
        ) == len(PAIRS)
        # A -30 at home, won the last three, won by 38 -> covers, both seasons. C -3 at D is a
        # trophy game too, but the series is split, so it is a row that does not qualify.
        assert res["record"]["n"] == 2 and res["record"]["wins"] == 2
        assert res["drops"] == {"universe": 4}
        assert res["secondary"]["qualifying_share"] == 0.5
    elif row_id == L.BENNETT:
        assert ("rankings", 2018, "postseason") in client.calls
        assert res["record"]["n"] == 2  # fade A (-30) twice; A won by 38 -> losses
        assert res["record"]["losses"] == 2
    elif row_id == L.TV:
        assert res["record"]["n"] == 2  # game 2 on CBS, 30 under 50, both seasons
        assert res["record"]["wins"] == 2
    else:
        assert res["record"]["n"] == 2 and res["record"]["wins"] == 2  # 52 over 50
    row = find_row(parse_registry(), row_id)
    stem = mod.write_reports(tmp_path, row, res, client.calls_remaining)
    md = stem.with_suffix(".md").read_text()
    assert row.criterion in md  # quoted verbatim
    body = json.loads(stem.with_suffix(".json").read_text())
    assert body["row"] == row_id and body["cfbd_calls_left"] == 1234 and "rows" not in body
    assert stem.with_suffix(".csv").exists()


def test_holm_mode_combines_reports_and_refuses_a_second_look(tmp_path, capsys):
    mod = _script()
    a = tmp_path / "a.json"
    a.write_text(json.dumps({"row": L.ARSCOTT, "record": {"p": 0.001}}))
    b = tmp_path / "b.json"
    b.write_text(json.dumps({"row": L.TV, "record": {"p": 0.009}}))
    assert mod.main(["--holm", str(a), str(b), "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "2 of 6 run" in out and "PASS" in out
    with pytest.raises(SystemExit):
        mod.main(["--holm", str(a), str(a), "--out", str(tmp_path)])


def test_main_needs_exactly_one_mode():
    mod = _script()
    with pytest.raises(SystemExit):
        mod.main([])
