"""Beat Vegas dashboard — first-half unders.

Run:  streamlit run beatvegas/dashboard/app.py

Sections: weekly opportunity board, line-movement charts, the graded ledger
(market + your own picks), and the research/backtest verdict. Degrades cleanly
when tables are empty (e.g. offseason, before any lines are captured).
"""
from __future__ import annotations

import json
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from beatvegas.db.store import get_engine, init_db

st.set_page_config(page_title="Beat Vegas — 1H Unders", layout="wide")
init_db()
ENGINE = get_engine()


@st.cache_data(ttl=120)
def q(sql: str, params: tuple = ()) -> pd.DataFrame:
    try:
        return pd.read_sql(sql, ENGINE, params=params)
    except Exception as e:  # noqa: BLE001
        st.warning(f"query failed: {e}")
        return pd.DataFrame()


def _default_season() -> int:
    now = datetime.utcnow()
    return now.year if now.month >= 6 else now.year - 1


def _score_color(score) -> str:
    if score is None:
        return "#6b7280"
    if score >= 60:
        return "#16a34a"          # strong under lean (green)
    if score >= 53:
        return "#65a30d"          # lean (lime)
    if score >= 47:
        return "#ca8a04"          # neutral-ish (amber)
    if score >= 40:
        return "#ea580c"          # lean over (orange)
    return "#dc2626"              # over (red)


def _chip(label: str, value: str, hint: str = "") -> str:
    return (f"<span style='display:inline-block;background:#1f2937;color:#e5e7eb;"
            f"border:1px solid #374151;border-radius:999px;padding:3px 10px;"
            f"margin:2px;font-size:0.82rem;' title='{hint}'>"
            f"<b style='color:#9ca3af'>{label}</b>&nbsp;{value}</span>")


def render_card(row: pd.Series) -> None:
    f = {}
    try:
        f = json.loads(row.get("factors_json") or "{}")
    except Exception:  # noqa: BLE001
        pass
    score = row.get("under_score")
    color = _score_color(score)
    proj = f.get("proj_1h_total")
    line = f.get("line")
    prob = row.get("under_probability")
    prob_txt = f"{prob*100:.0f}%" if prob is not None else "—"
    open_line, cur_line = row.get("open_line"), row.get("cur_line")
    line_now = cur_line if cur_line is not None else line
    move = (f"{open_line:.1f} → {cur_line:.1f}"
            if open_line is not None and cur_line is not None
            and abs(open_line - cur_line) >= 0.01 else None)

    with st.container(border=True):
        left, right = st.columns([1, 3])
        with left:
            st.markdown(
                f"<div style='text-align:center'>"
                f"<div style='font-size:0.7rem;color:#9ca3af'>UNDER SCORE</div>"
                f"<div style='font-size:3rem;font-weight:800;line-height:1;"
                f"color:{color}'>{score if score is not None else '—'}</div>"
                f"<div style='font-size:0.7rem;color:#9ca3af'>#{int(row['rank'])} "
                f"· 50 = breakeven</div></div>", unsafe_allow_html=True)
        with right:
            st.markdown(
                f"#### {row['away_team']} @ {row['home_team']}"
                f"&nbsp;&nbsp;<span style='font-size:0.8rem;color:#9ca3af'>"
                f"Wk {int(row['week'])}</span>", unsafe_allow_html=True)
            line_txt = f"{line_now:.1f}" if line_now is not None else "—"
            st.markdown(
                f"**Current 1H line:** {line_txt}"
                + (f" <span style='color:#9ca3af'>({move})</span>" if move else "")
                + f" &nbsp;·&nbsp; **Model: under {prob_txt}** "
                "<span style='font-size:0.75rem;color:#9ca3af'>"
                "(breakeven 52%)</span>", unsafe_allow_html=True)
            # BV line (market-blind) vs Vegas + gap, with the 80% band and the
            # gap in units of the line's own noise (σ). |z|<1 = noise, not edge.
            bv = f.get("bv_line")
            bv_lo, bv_hi, bv_sigma = f.get("bv_lo"), f.get("bv_hi"), f.get("bv_sigma")
            vegas = line_now
            gap = (vegas - bv) if (vegas is not None and bv is not None) else f.get("bv_gap")
            z = (gap / bv_sigma) if (gap is not None and bv_sigma) else None
            significant = z is not None and abs(z) >= 1
            gap_color = ("#6b7280" if gap is None or not significant else
                         "#65a30d" if gap > 0 else "#dc2626")
            band = (f" ({bv_lo:.0f}–{bv_hi:.0f})"
                    if bv_lo is not None and bv_hi is not None else "")
            z_txt = (f" <span style='color:{'#d1d5db' if significant else '#6b7280'}'>"
                     f"({z:+.1f}σ{'' if significant else ' · noise'})</span>"
                     if z is not None else "")
            qb_home, qb_away = f.get("qb_out_home"), f.get("qb_out_away")
            if qb_home or qb_away:
                who = " · ".join(t for t, flag in
                                 [(row['away_team'], qb_away), (row['home_team'], qb_home)] if flag)
                st.markdown(
                    f"<span style='font-size:0.8rem;color:#fbbf24'>⚠ QB OUT · {who} "
                    "<span style='color:#a16207'>(live, unofficial)</span></span>",
                    unsafe_allow_html=True)
            st.markdown(
                f"<span style='font-size:0.85rem;color:#9ca3af'>"
                f"BV {('%.1f' % bv) if bv is not None else '—'}{band} · "
                f"Vegas {('%.1f' % vegas) if vegas is not None else '—'} · gap "
                f"</span><span style='font-size:0.85rem;color:{gap_color}'>"
                f"{('%+.1f' % gap) if gap is not None else '—'}</span>{z_txt}"
                "<br><span style='font-size:0.7rem;color:#6b7280'>BV = our own "
                "MARKET-BLIND 1H number (no Vegas input); the band is the 80% range. "
                "A gap only counts past ~1σ — see Research → Gap vs CLV</span>",
                unsafe_allow_html=True)
            proj_txt = f"{proj:.1f}" if proj is not None else "—"
            chips = [
                _chip("Pace", f.get("pace") or "live ✦",
                      "Combined seconds/play + plays/game (TeamRankings)"),
                _chip("Weather", f.get("weather") or "live ✦",
                      "Temp / wind / precip near kickoff (Open-Meteo)"),
                _chip("Def eff", f"{f.get('def_ppa')}" if f.get("def_ppa") is not None else "—",
                      "Combined defensive PPA allowed (lower = stronger D)"),
                _chip("Off eff", f"{f.get('off_ppa')}" if f.get("off_ppa") is not None else "—",
                      "Combined offensive PPA (lower = less explosive)"),
                _chip("1H hist",
                      (f"{f.get('fh_home_pf')}/{f.get('fh_home_pa')} · "
                       f"{f.get('fh_away_pf')}/{f.get('fh_away_pa')}")
                      if f.get("fh_home_pf") is not None else "—",
                      "Season-to-date 1H pts for/against (home · away)"),
                _chip("Spot", f.get("spot") or "—",
                      "Rest days (home/away) · away travel · ~local kickoff "
                      "(context only — not a model input)"),
                _chip("Hist proj", proj_txt,
                      "Naive 1H projection from scoring history (context only — "
                      "the model, not this, drives the score)"),
            ]
            st.markdown("".join(chips), unsafe_allow_html=True)


st.title("🏈 Beat Vegas — College Football First-Half Unders")
st.caption("Research & decision-support only. No bets are placed or automated.")

seasons = q("SELECT DISTINCT season FROM games ORDER BY season DESC")
season_list = seasons["season"].tolist() if not seasons.empty else [_default_season()]
season = st.sidebar.selectbox("Season", season_list, index=0)

tab_board, tab_moves, tab_study, tab_picks, tab_ledger, tab_research = st.tabs(
    ["📋 Opportunities", "📈 Line movement", "📐 Line Study",
     "✍️ My Picks", "💰 Ledger", "🔬 Research"])

# ---------------------------------------------------------------- board
with tab_board:
    st.subheader(f"Ranked first-half under board — {season}")
    st.caption("Under Score: 50 = the −110 breakeven. Higher = stronger model "
               "lean to the under. Sorted strongest first.")
    preds = q("""
        SELECT p.game_id, p.under_score, p.under_probability, p.rank, p.factors_json,
               g.week, g.away_team, g.home_team, g.full_game_total
        FROM predictions p JOIN games g ON g.id = p.game_id
        WHERE g.season = ?
          AND p.model_version = (SELECT model_version FROM predictions
                                 ORDER BY created_at DESC LIMIT 1)
        ORDER BY p.rank
    """, (int(season),))
    if preds.empty:
        st.info("No ranked games yet for this season. During the season, run "
                "`poll_lines.py` then the scoring step to populate this board "
                "(books post 1H totals around game week).")
    else:
        # current consensus line + opening, per game, from snapshots
        snaps = q("""SELECT game_id, book, line, captured_at FROM odds_snapshots
                     WHERE market='1H_total'""")
        open_line, cur_line = {}, {}
        if not snaps.empty:
            snaps = snaps.sort_values("captured_at")
            for gid, grp in snaps.groupby("game_id"):
                firsts = grp.groupby("book").first()["line"]
                lasts = grp.groupby("book").last()["line"]
                open_line[gid] = float(firsts.median())
                cur_line[gid] = float(lasts.median())
        preds["open_line"] = preds["game_id"].map(open_line)
        preds["cur_line"] = preds["game_id"].map(cur_line)
        c1, c2 = st.columns(2)
        c1.metric("Games ranked", len(preds))
        strong = int((preds["under_score"] >= 53).sum())
        c2.metric("Model leans under (score ≥ 53)", strong)
        for _, row in preds.iterrows():
            render_card(row)

# ------------------------------------------------------------- movement
with tab_moves:
    st.subheader("Line movement by book")
    games_with_moves = q("""
        SELECT g.id, g.week, g.away_team || ' @ ' || g.home_team AS matchup,
               COUNT(*) AS snaps
        FROM games g JOIN odds_snapshots o ON o.game_id=g.id
        WHERE g.season=? AND o.market='1H_total'
        GROUP BY g.id HAVING snaps>1 ORDER BY g.week
    """, (int(season),))
    if games_with_moves.empty:
        st.info("No multi-snapshot games yet — movement charts appear once a "
                "line has been polled more than once.")
    else:
        label = games_with_moves.apply(
            lambda r: f"wk{r['week']}: {r['matchup']} ({r['snaps']} snaps)", axis=1)
        choice = st.selectbox("Game", options=list(games_with_moves["id"]),
                              format_func=lambda gid: label[
                                  games_with_moves.index[games_with_moves["id"] == gid][0]])
        snaps = q("""SELECT captured_at, book, line FROM odds_snapshots
                     WHERE game_id=? AND market='1H_total'
                     ORDER BY captured_at""", (int(choice),))
        if not snaps.empty:
            snaps["captured_at"] = pd.to_datetime(snaps["captured_at"])
            pivot = snaps.pivot_table(index="captured_at", columns="book",
                                      values="line", aggfunc="last")
            st.line_chart(pivot)
            st.dataframe(snaps, width="stretch", hide_index=True)

# ----------------------------------------------------------- line study
with tab_study:
    from beatvegas.analysis.line_study import BREAKEVEN_PCT, line_study

    @st.cache_data(ttl=120)
    def _study(season: int, min_games: int):
        return line_study(season, min_games=min_games)

    st.subheader(f"Which opening 1H line cashed unders most — {season}")
    cc1, cc2 = st.columns([2, 1])
    min_games = cc1.slider("Minimum games per line", 5, 60, 30, step=5)
    highlight = cc2.number_input("Highlight line", value=24.5, step=0.5)
    study = _study(int(season), int(min_games))
    if study.empty:
        st.info(f"No line buckets with ≥ {min_games} games for {season}.")
    else:
        real = (study["line_source"] == "real_open").any()
        src = ("real opening lines" if real else "PROXY lines (0.52×full total)")
        st.caption(f"Bucketed by **{src}**. Breakeven vs −110 = {BREAKEVEN_PCT}%. "
                   + ("" if real else "⚠️ On proxy data the cross-line ranking "
                      "partly reflects game-total level, not a standalone "
                      "tradeable signal — directional until real lines accrue."))
        # color-coded bar chart vs breakeven
        chart = study.sort_values("line")
        fig, ax = plt.subplots(figsize=(9, 3.2))
        colors = ["#16a34a" if p >= BREAKEVEN_PCT else "#dc2626"
                  for p in chart["under_pct"]]
        ax.bar(chart["line"].astype(str), chart["under_pct"], color=colors)
        ax.axhline(BREAKEVEN_PCT, color="#9ca3af", linestyle="--", linewidth=1)
        ax.set_ylabel("Under %"); ax.set_xlabel("Opening 1H line")
        ax.set_ylim(0, max(70, chart["under_pct"].max() + 5))
        plt.xticks(rotation=45, ha="right", fontsize=8)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        st.pyplot(fig)

        hl = study[study["line"] == float(highlight)]
        if not hl.empty:
            r = hl.iloc[0]
            verdict = "beats" if r["under_pct"] >= BREAKEVEN_PCT else "below"
            st.metric(f"Under {highlight}", f"{r['under_pct']}%",
                      f"{int(r['under'])}/{int(r['games'])} · {verdict} breakeven")
        else:
            st.caption(f"No bucket at {highlight} with ≥ {min_games} games.")
        st.dataframe(study.sort_values("under_pct", ascending=False),
                     width="stretch", hide_index=True)

# ------------------------------------------------------------- my picks
with tab_picks:
    from datetime import datetime as _dt

    from beatvegas.db.models import ManualPick
    from beatvegas.db.store import session_scope

    st.subheader(f"Log a first-half under bet — {season}")
    slate = q("""
        SELECT p.game_id, p.line_used, p.under_score,
               g.week, g.away_team, g.home_team
        FROM predictions p JOIN games g ON g.id = p.game_id
        WHERE g.season = ?
          AND p.model_version = (SELECT model_version FROM predictions
                                 ORDER BY created_at DESC LIMIT 1)
        ORDER BY p.rank
    """, (int(season),))
    if slate.empty:
        st.info("No scored games yet — run `weekly_update.py` for this season.")
    else:
        labels = {int(r.game_id): f"wk{int(r.week)}: {r.away_team} @ {r.home_team}"
                  f"  (score {int(r.under_score)})"
                  for r in slate.itertuples()}
        with st.form("log_pick", clear_on_submit=True):
            gid = st.selectbox("Game", options=list(labels),
                               format_func=lambda g: labels[g])
            default_line = float(slate.set_index("game_id").loc[gid, "line_used"]
                                 or 24.5)
            c1, c2, c3 = st.columns(3)
            line = c1.number_input("Your line", value=default_line, step=0.5)
            stake = c2.number_input("Stake (units)", value=1.0, step=0.5, min_value=0.0)
            price = c3.number_input("Price", value=-110, step=5)
            submitted = st.form_submit_button("Log UNDER bet")
        if submitted:
            row = slate.set_index("game_id").loc[gid]
            with session_scope() as s:
                s.add(ManualPick(
                    game_id=int(gid), season=int(season), week=int(row["week"]),
                    home_team=row["home_team"], away_team=row["away_team"],
                    side="under", line=float(line), price=int(price),
                    stake=float(stake), placed_at=_dt.utcnow(), graded=False))
            q.clear()
            st.success(f"Logged UNDER {line:g} on {row['away_team']} @ "
                       f"{row['home_team']}")
            st.rerun()

        # News/injury context for the selected game (ESPN — display only)
        @st.cache_data(ttl=900)
        def _news_ctx(home, away):
            from beatvegas.sources.espn import game_context
            return game_context(home, away)

        srow = slate.set_index("game_id").loc[gid]
        with st.expander("📰 News & injuries (ESPN — context only, not in the model)"):
            ctx = _news_ctx(srow["home_team"], srow["away_team"])
            any_shown = False
            for side in ("away", "home"):
                c = ctx.get(side, {})
                if c.get("injuries") or c.get("news"):
                    any_shown = True
                    st.markdown(f"**{c.get('school')}**")
                    for inj in c.get("injuries", []):
                        st.markdown(f"- 🩹 {inj}")
                    for h in c.get("news", [])[:3]:
                        st.markdown(f"- 📰 {h}")
            if not any_shown:
                st.caption("No current news/injuries found (offseason, or ESPN "
                           "unavailable). CFB injury data is unofficial/unreliable.")

    st.markdown("**Your bets this season**")
    mine = q("""SELECT week, away_team, home_team, line, price, stake,
                       graded, result, units, clv FROM manual_picks
                WHERE season=? ORDER BY graded, week""", (int(season),))
    if mine.empty:
        st.caption("No picks logged yet.")
    else:
        g = mine[mine["graded"] == 1]
        if not g.empty:
            wins = int((g["result"] == "under").sum())
            pushes = int((g["result"] == "push").sum())
            dec = len(g) - pushes
            m1, m2, m3 = st.columns(3)
            m1.metric("Record", f"{wins}-{dec-wins}" + (f"-{pushes}P" if pushes else ""),
                      f"{100*wins/dec:.0f}%" if dec else "—")
            m2.metric("Units", f"{g['units'].sum():+.2f}")
            m3.metric("Avg CLV", f"{g['clv'].dropna().mean():+.2f}"
                      if g['clv'].notna().any() else "—")
        st.dataframe(mine, width="stretch", hide_index=True)

# --------------------------------------------------------------- ledger
with tab_ledger:
    st.subheader(f"Graded ledger — {season}")
    st.caption("Market = under vs real closing line · Model = the model's leans "
               "(score ≥ 53) at the line it picked · You = your logged bets.")

    def _record(under_series, units_series, clv_series, push_series=None):
        n = len(under_series)
        pushes = int(push_series.sum()) if push_series is not None else 0
        dec = n - pushes
        wins = int(under_series.sum())
        return {
            "record": f"{wins}-{dec-wins}" + (f"-{pushes}P" if pushes else ""),
            "hit": f"{100*wins/dec:.1f}%" if dec else "—",
            "units": f"{units_series.sum():+.2f}",
            "clv": f"{clv_series.dropna().mean():+.2f}" if clv_series.notna().any() else "—",
        }

    res = q("""SELECT model_version, under_hit, units, clv FROM results r
               JOIN games g ON g.id=r.game_id WHERE g.season=?""", (int(season),))
    mine = q("""SELECT graded, result, units, clv, week, line, price,
                       away_team, home_team FROM manual_picks WHERE season=?""",
             (int(season),))

    cM, cm, cY = st.columns(3)
    with cM:
        st.markdown("**📊 Market**")
        m = res[res["model_version"] == "market"]
        if m.empty:
            st.caption("Run grade.py after games.")
        else:
            r = _record(m["under_hit"], m["units"], m["clv"])
            st.metric("Hit", r["hit"], r["record"])
            st.metric("Units", r["units"]); st.metric("Avg CLV", r["clv"])
    with cm:
        st.markdown("**🤖 Model**")
        md = res[res["model_version"] == "gbm_v1"]
        if md.empty:
            st.caption("Run weekly_update + grade.")
        else:
            r = _record(md["under_hit"], md["units"], md["clv"])
            st.metric("Hit", r["hit"], r["record"])
            st.metric("Units", r["units"]); st.metric("Avg CLV", r["clv"])
    with cY:
        st.markdown("**✍️ You**")
        gmine = mine[mine["graded"] == 1] if not mine.empty else mine
        if gmine.empty:
            st.caption("Log bets in the My Picks tab.")
        else:
            r = _record(gmine["result"] == "under", gmine["units"], gmine["clv"],
                        push_series=(gmine["result"] == "push"))
            st.metric("Hit", r["hit"], r["record"])
            st.metric("Units", r["units"]); st.metric("Avg CLV", r["clv"])

    if not mine.empty:
        st.markdown("**Your bets**")
        st.dataframe(mine, width="stretch", hide_index=True)

# ------------------------------------------------------------- research
with tab_research:
    st.subheader("The edge question")
    base = q("""SELECT first_half_total, full_game_total FROM games
                WHERE first_half_total IS NOT NULL AND full_game_total>0""")
    if not base.empty:
        ratio = (base["first_half_total"] / base["full_game_total"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Games analyzed", f"{len(base):,}")
        c2.metric("Realized 1H / full (mean)", f"{ratio.mean():.3f}")
        c3.metric("Median", f"{ratio.median():.3f}")
        st.markdown(
            "First halves realize **~52% of the full-game total** — right where "
            "books price the 1H line. Blanket and model-selected 1H unders did "
            "**not** reliably beat the −110 breakeven (52.4%) against a proxy line, "
            "and the apparent signal sits inside the ±1.5 pt proxy uncertainty.\n\n"
            "**Verdict:** no edge is *confirmable* on free historical data — there "
            "are no historical 1H lines to grade against. The real test is the "
            "live ledger above, built from real first-half lines captured this "
            "season.")
    else:
        st.info("Load history with `scripts/backfill.py` to see calibration.")

    st.divider()
    st.markdown("**Gap vs CLV** — do our biggest BV-vs-Vegas gaps earn closing-line value?")
    st.caption("Gap = Vegas line − BV line (under direction). If the BV number "
               "finds value, lines on big-gap picks move toward us before close "
               "(mean CLV rises with the bucket). Flat/negative ⇒ blind spots, "
               "not edges. CLV>0 = under closed at a softer number.")
    # 'market' ledger = consensus open as bet line, close-open as CLV: measures
    # whether the LINE moves toward our BV number by close. BV line from gbm_v1.
    gap_rows = q("""
        SELECT (r.line_used - p.bv_line) AS gap, r.clv, r.units, r.under_hit
        FROM results r JOIN predictions p ON p.game_id = r.game_id
        WHERE r.model_version = 'market' AND p.model_version = 'gbm_v1'
          AND r.clv IS NOT NULL AND p.bv_line IS NOT NULL AND r.line_used IS NOT NULL
    """)
    if gap_rows.empty:
        st.info("No graded games with a BV line and real closing line yet — fills "
                "in as 1H lines are polled (`poll_lines.py`) and graded (`grade.py`).")
    else:
        edges = [(-1e9, 0, "<0"), (0, 1, "0–1"), (1, 2, "1–2"),
                 (2, 3, "2–3"), (3, 1e9, "3+")]
        buckets = []
        for lo, hi, label in edges:
            b = gap_rows[(gap_rows["gap"] >= lo) & (gap_rows["gap"] < hi)]
            buckets.append({
                "Gap bucket": label, "N": len(b),
                "Mean gap": round(b["gap"].mean(), 2) if len(b) else None,
                "Mean CLV": round(b["clv"].mean(), 2) if len(b) else None,
                "Mean units": round(b["units"].mean(), 2) if len(b) else None,
                "Under %": round(100 * b["under_hit"].mean(), 1) if len(b) else None,
            })
        st.dataframe(pd.DataFrame(buckets), width="stretch", hide_index=True)

    st.divider()
    st.markdown("**BV-line calibration (out-of-fold)** — mean residual = actual − BV, per segment")
    st.caption("Near 0 = unbiased. A persistent positive residual means the BV "
               "line runs low (would falsely scream 'under'). The first post-2023 "
               "season can't be de-biased from data that doesn't exist yet — "
               "surfaced here, not hidden.")
    cal = q("""SELECT metrics_json FROM model_runs WHERE metrics_json IS NOT NULL
               ORDER BY created_at DESC LIMIT 5""")
    bv_res = None
    for js in cal["metrics_json"] if not cal.empty else []:
        try:
            bv_res = json.loads(js).get("bv_residual")
        except Exception:  # noqa: BLE001
            bv_res = None
        if bv_res:
            break
    if not bv_res:
        st.caption("No calibration logged yet — run `scripts/retrain.py`.")
    else:
        rows_c = [{"Segment": "overall", "N": bv_res.get("n"),
                   "Mean residual": bv_res.get("overall_mean_residual")}]
        for grp in ("by_era", "by_tempo", "by_dome"):
            for k, v in (bv_res.get(grp) or {}).items():
                if isinstance(v, dict):
                    rows_c.append({"Segment": k, "N": v.get("n"),
                                   "Mean residual": v.get("mean_residual")})
        st.dataframe(pd.DataFrame(rows_c), width="stretch", hide_index=True)

    st.divider()
    st.markdown("**Model runs over time** (does it sharpen as seasons are added?)")
    runs = q("""SELECT created_at, version, train_window, test_window,
                       metrics_json FROM model_runs ORDER BY created_at""")
    if runs.empty:
        st.caption("No runs logged yet — run `scripts/retrain.py`.")
    else:
        def _m(js, k):
            try:
                return json.loads(js).get(k)
            except Exception:  # noqa: BLE001
                return None
        runs["top_under_pct"] = runs["metrics_json"].apply(lambda j: _m(j, "top_under_pct"))
        runs["top_roi"] = runs["metrics_json"].apply(lambda j: _m(j, "top_roi"))
        runs["baseline_under_pct"] = runs["metrics_json"].apply(
            lambda j: _m(j, "baseline_under_pct"))
        st.dataframe(
            runs[["created_at", "train_window", "test_window",
                  "baseline_under_pct", "top_under_pct", "top_roi"]],
            width="stretch", hide_index=True)
