// What the site MUST show for the fixture week, derived by a plain-JS port of
// the pure rules in web/lib (verdict.ts, edge.ts, lineCheck.ts, board.ts,
// homeBoard.ts, answerBar.ts) and beatvegas/card.py::build_card.
//
// A port rather than an import for one reason: seed.mjs runs under plain
// `node` (no TypeScript) and needs the card payload, which has to agree with
// what the board computes live from the same rows. lib/e2eFixture.test.ts
// (vitest) holds this file to the TypeScript originals game by game -- slateBar
// against the shared golden vectors, edgeScore/priceSentence/deriveReason on
// every fixture game -- so the port cannot drift from the site.
//
// Everything here is a function of the week (and so of `now`); nothing is
// typed in by hand except the ledger rows at the bottom.

import { etMinutesOfDay, etParts, HR } from "./week.mjs";

// --- constants (lib/verdict.ts, lib/grade.ts, lib/lineCheck.ts, lib/devig.ts) ---

export const BET_GAP_PTS = 1.75;
export const PCT_SHARE = 0.2;
export const HR_OFF_MARKET_PTS = 0.5;
export const EV_FLOOR = -0.05;
export const BET_MIN_EV = EV_FLOOR;
export const SCORE_BET_MIN = 70;
export const SCORE_WATCH_MIN = 55;
export const WEEKLY_BET_CAP = 5;
export const MIN_GAMES_FOR_REAL_MONEY = 2;
export const SKEW_REJECT_PRICE = -160;
export const FAIR_PRICE_LINE_WINDOW = 0.5;
export const FAIR_PRICE_WIDE_WINDOW = 1.5;
export const PRICE_EDGE_EV = 0.005;

// --- lib/format.ts ---------------------------------------------------------

export const round2 = (n) => Math.round(n * 100) / 100;
export const fmt = (n, dp = 1) =>
  n === null || n === undefined ? "—" : n.toFixed(dp);
export const american = (p) => (p > 0 ? `+${p}` : `${p}`);
export function median(xs) {
  if (xs.length === 0) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}
/** Round UP to the next half point (lib/edge.ts::roundHalfUp). */
export const roundHalfUp = (x) => Math.ceil(x * 2 - 1e-9) / 2;

// --- lib/devig.ts ----------------------------------------------------------

export const americanToDecimal = (p) =>
  p < 0 ? 1 + 100 / Math.abs(p) : 1 + p / 100;
export const americanToProb = (p) => 1 / americanToDecimal(p);
export function devigTwoWay(over, under) {
  const pOver = americanToProb(over);
  const pUnder = americanToProb(under);
  const total = pOver + pUnder;
  return {
    fairOver: pOver / total,
    fairUnder: pUnder / total,
    hold: total - 1,
  };
}
export const evUnder = (fairUnder, price) =>
  fairUnder * (americanToDecimal(price) - 1) - (1 - fairUnder);
export function isCentredQuote(over, under) {
  for (const p of [over, under]) {
    if (p == null) continue;
    if (p < SKEW_REJECT_PRICE) return false;
  }
  return true;
}

// --- lib/verdict.ts::slateBar (pinned to tests/fixtures/slate_bar_vectors.json) ---

export function slateBar(gaps, share = PCT_SHARE) {
  const vals = gaps
    .filter((g) => typeof g === "number" && Number.isFinite(g))
    .sort((a, b) => b - a);
  if (vals.length === 0) return null;
  const k = Math.max(1, Math.round(share * vals.length));
  return vals[k - 1];
}

// --- lib/edge.ts::breakEvenPrice ------------------------------------------

export function breakEvenPrice(fairUnder, floor = BET_MIN_EV) {
  for (let p = -1000; p <= 1000; p += 5) {
    if (p === -100 || (p > -100 && p < 100)) continue;
    if (evUnder(fairUnder, p) >= floor) return p;
  }
  return null;
}

// --- lib/lineCheck.ts -------------------------------------------------------

export function evVerdictFor(ev) {
  if (ev === null) return "na";
  if (ev > PRICE_EDGE_EV) return "pos";
  if (ev < EV_FLOOR) return "neg";
  return "fair";
}

/** Latest 1H quote per book for a game: {book: {line, over, under}}. */
export function latestByBook(g) {
  const out = new Map();
  if (g.hr && g.hr.length) {
    const last = g.hr[g.hr.length - 1];
    out.set(HR, { line: last.line, over: last.over, under: last.under });
  }
  for (const [book, [line, over, under]] of Object.entries(g.books)) {
    // lineCheck's SQL drops an off-centre rung from every book but Hard Rock.
    if (!isCentredQuote(over, under)) continue;
    out.set(book, { line, over, under });
  }
  return out;
}

export function fairPriceWindow(hrVsMarket) {
  return {
    below:
      hrVsMarket !== null && hrVsMarket > 0
        ? FAIR_PRICE_WIDE_WINDOW
        : FAIR_PRICE_LINE_WINDOW,
    above: FAIR_PRICE_LINE_WINDOW,
  };
}

/** The market's no-vig fair P(under) at Hard Rock's number (books path; the fixture has no exchanges). */
export function marketFairUnderAt(hrLine, byBook) {
  if (hrLine === null) return null;
  const otherLines = [...byBook.entries()]
    .filter(([k]) => k !== HR)
    .map(([, o]) => o.line);
  const others = median(otherLines);
  const { below, above } = fairPriceWindow(
    others === null ? null : hrLine - others,
  );
  const fair = [];
  for (const [k, o] of byBook) {
    if (k === HR || k === "fliff" || o.over == null || o.under == null)
      continue;
    if (o.line - hrLine <= above && hrLine - o.line <= below) {
      fair.push(devigTwoWay(o.over, o.under).fairUnder);
    }
  }
  return median(fair);
}

/** lib/lineCheck.ts::getLineCheck, one game; null when no 1H quote exists. */
export function lineCheckFor(g) {
  const byBook = latestByBook(g);
  if (byBook.size === 0) return null;
  const hr = byBook.get(HR) ?? null;
  const hrLine = hr ? hr.line : null;
  const lines = [...byBook.values()].map((o) => o.line);
  const hrUnderPrice = hr ? hr.under : null;
  const hrOverPrice = hr ? hr.over : null;
  const marketFairUnder = marketFairUnderAt(hrLine, byBook);
  const ev =
    marketFairUnder !== null && hrUnderPrice !== null
      ? evUnder(marketFairUnder, hrUnderPrice)
      : null;
  return {
    hrLine,
    hrUnderPrice,
    hrOverPrice,
    hrCentred: hr ? isCentredQuote(hrOverPrice, hrUnderPrice) : false,
    best: Math.max(...lines),
    median: median(lines),
    marketFairUnder,
    ev,
    evVerdict: evVerdictFor(ev),
    books: [...byBook.keys()],
  };
}

/** lib/board.ts::consensusLines, one game: each book's first and last centred capture -> medians. */
export function consensusFor(g) {
  const firsts = [];
  const lasts = [];
  if (g.hr && g.hr.length) {
    const caps = g.hr.filter((c) => isCentredQuote(c.over, c.under));
    if (caps.length) {
      firsts.push(caps[0].line);
      lasts.push(caps[caps.length - 1].line);
    }
  }
  for (const [, [line, over, under]] of Object.entries(g.books)) {
    if (!isCentredQuote(over, under)) continue;
    firsts.push(line);
    lasts.push(line);
  }
  return { open: median(firsts), cur: median(lasts) };
}

// --- lib/verdict.ts / lib/edge.ts -----------------------------------------

export function deriveReason(
  hasModel,
  hrGap,
  priceEdgeOnly,
  bar = BET_GAP_PTS,
) {
  if (hasModel && hrGap !== null && hrGap >= bar && hrGap > 0)
    return "model_gap";
  if (priceEdgeOnly) return "price_edge";
  return "manual";
}

/** verdict.ts::priceSentence, word for word. */
export function priceSentence(i) {
  if (i.hrLine === null) {
    return "Hard Rock has not posted a first-half line yet.";
  }
  const at =
    i.hrUnderPrice === null
      ? `under ${fmt(i.hrLine)}`
      : `under ${fmt(i.hrLine)} at ${american(i.hrUnderPrice)}`;
  if (i.ev === null) {
    return i.hrUnderPrice === null
      ? `Hard Rock has the under at ${fmt(i.hrLine)} but no price on it yet, so there is nothing to compare.`
      : `Hard Rock has the under at ${fmt(i.hrLine)}. Not enough other books are at that number to compare the price.`;
  }
  const pctTxt = fmt(Math.abs(i.ev) * 100);
  switch (i.evVerdict) {
    case "pos":
      return `Hard Rock’s ${at} pays about ${pctTxt}% more than the fair price. Fair price = the other books and the exchanges with the vig taken out.`;
    case "neg":
      return `Hard Rock’s ${at} pays about ${pctTxt}% less than the fair price. You would be paying extra vig.`;
    default:
      return `Hard Rock’s ${at} is priced about the same as the rest of the market.`;
  }
}

/** card.py::_gap_sentence (model rows only; every fixture game has a model). */
export function gapSentence(bv, hrLine, marketLine, reference, gap) {
  if (hrLine !== null) {
    const hrGap = round2(hrLine - bv);
    const direction =
      hrGap > 0
        ? "above our number, which leans under"
        : hrGap < 0
          ? "below our number, which leans over"
          : "right on our number";
    const market =
      marketLine !== null && Math.abs(marketLine - hrLine) >= 0.05
        ? ` (the market consensus is ${fmt(marketLine)}).`
        : ".";
    return `Hard Rock has the first half at ${fmt(hrLine)}; our number is ${fmt(bv)}${market} Hard Rock’s line is ${fmt(Math.abs(hrGap))} points ${direction}.`;
  }
  const basis = marketLine !== null ? marketLine : reference;
  if (basis === null || gap === null) {
    return `Our number for the first half is ${fmt(bv)}, but no Vegas line has been captured to compare it to.`;
  }
  const src =
    marketLine !== null
      ? "The market has (Hard Rock has not posted)"
      : "The estimated line is";
  const direction =
    gap > 0
      ? "above our number, which leans under"
      : gap < 0
        ? "below our number, which leans over"
        : "right on our number";
  return `${src} the first half at ${fmt(basis)}; our number is ${fmt(bv)}. The line is ${fmt(Math.abs(gap))} points ${direction}.`;
}

const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n));

/**
 * lib/edge.ts::edgeScore for one fixture game, given this slate's bar. The
 * EdgeInput the board builds (lib/homeBoard.ts) is assembled here from the
 * same rows: `check` is lineCheckFor, `cons` is consensusFor, the fallback line
 * is the model row's factors.line (= line_used).
 */
export function edgeFor(
  g,
  bar,
  check = lineCheckFor(g),
  cons = consensusFor(g),
) {
  const bv = g.bv;
  const hrLine = check ? check.hrLine : null;
  const hrUnderPrice = check ? check.hrUnderPrice : null;
  const ev = check ? check.ev : null;
  const evVerdict = check ? check.evVerdict : "na";
  const marketLine = cons.cur;
  const fallbackLine = lineUsedFor(g);
  const marketFairUnder = check ? check.marketFairUnder : null;
  const hrCentred = check ? check.hrCentred : null;
  const minGamesPlayed = Math.min(g.gamesPlayed.home, g.gamesPlayed.away);
  const qbOut = false;

  // verdictFor: the BET gate.
  const hrGap = hrLine !== null ? round2(hrLine - bv) : null;
  const centred = hrCentred ?? true;
  const inBand = hrGap !== null && centred && hrGap > 0 && hrGap >= bar;
  const liveLine = marketLine;
  let verdict = "PASS";
  if (
    hrGap !== null &&
    inBand &&
    liveLine !== null &&
    liveLine - hrLine > HR_OFF_MARKET_PTS
  ) {
    verdict = "WATCH";
  } else if (hrGap !== null && inBand && qbOut) {
    verdict = "WATCH";
  } else if (
    hrGap !== null &&
    inBand &&
    ev !== null &&
    ev >= BET_MIN_EV &&
    minGamesPlayed !== null &&
    minGamesPlayed < MIN_GAMES_FOR_REAL_MONEY
  ) {
    verdict = "WATCH";
  } else if (hrGap !== null && inBand && ev !== null && ev >= BET_MIN_EV) {
    verdict = "BET";
  } else if (hrGap !== null && inBand) {
    verdict = "WATCH";
  } else {
    const consensusGap = cons.cur !== null ? round2(cons.cur - bv) : 0;
    if (hrLine === null && consensusGap >= bar) verdict = "WATCH";
    else if (hrGap !== null && liveLine !== null && consensusGap >= bar)
      verdict = "WATCH";
    else if ((hrGap ?? consensusGap) >= 1.0 || evVerdict === "pos")
      verdict = "WATCH";
  }
  const reason = deriveReason(true, hrGap, false, bar);

  // edgeScore proper.
  const offMarket =
    hrLine !== null &&
    marketLine !== null &&
    marketLine - hrLine > HR_OFF_MARKET_PTS;
  const pricePos = evVerdict === "pos";
  const basis = hrLine ?? marketLine ?? fallbackLine;
  const lineBasis =
    hrLine !== null
      ? "hardrock"
      : marketLine !== null
        ? "market"
        : fallbackLine !== null
          ? "reference"
          : null;
  const gap = basis !== null ? round2(basis - bv) : null;
  const killLine = roundHalfUp(bv + bar);
  const killPrice =
    marketFairUnder !== null ? breakEvenPrice(marketFairUnder) : null;
  const score = clamp(
    Math.floor(50 + ((SCORE_BET_MIN - 50) / bar) * (gap ?? 0)),
    0,
    100,
  );

  let tier;
  let blocker = null;
  if (verdict === "BET") tier = "BET";
  else if (score >= SCORE_WATCH_MIN) {
    tier = "EDGE";
    if (hrLine === null) blocker = "no_hr_line";
    else if (offMarket) blocker = "off_market";
    else if (ev === null) blocker = "no_fair_price";
    else if (ev < BET_MIN_EV) blocker = "price";
    else if (qbOut) blocker = "qb_out";
    else if (
      minGamesPlayed !== null &&
      minGamesPlayed < MIN_GAMES_FOR_REAL_MONEY
    )
      blocker = "early_season";
    else blocker = "gap";
  } else tier = "PASS";

  let action;
  if (tier === "BET") {
    const at = hrUnderPrice !== null ? ` at ${american(hrUnderPrice)}` : "";
    action = `Bet one unit: first-half under ${fmt(hrLine)}${at} on Hard Rock.`;
  } else if (blocker === "no_hr_line" || basis === null) {
    if (basis === null) {
      action = `Not yet — no first-half line anywhere. It becomes a bet at under ${fmt(killLine)} or higher.`;
    } else {
      const at =
        killPrice !== null ? `, at ${american(killPrice)} or better` : "";
      action = `Not yet — Hard Rock has no first-half line. It becomes a bet at under ${fmt(killLine)} or higher${at}.`;
    }
  } else if (blocker === "off_market") {
    const diff = round2(marketLine - hrLine);
    action = `Not yet — Hard Rock’s ${fmt(hrLine)} is ${fmt(diff)} below the market line of ${fmt(marketLine)}. You would be giving up points, and Hard Rock can void a bet that far off the market. Bet it if Hard Rock moves to ${fmt(marketLine - HR_OFF_MARKET_PTS)} or higher.`;
  } else if (blocker === "price") {
    const needs = `${american(killPrice ?? -110)} or better`;
    const hr = hrUnderPrice !== null ? american(hrUnderPrice) : "not posted";
    action = `Not yet — Hard Rock’s price is ${hr}; needs ${needs}.`;
  } else if (blocker === "no_fair_price") {
    action =
      hrUnderPrice === null
        ? `Not yet — Hard Rock has not priced its ${fmt(hrLine)} under. Paper only until it does.`
        : `Not yet — no other book is at ${fmt(hrLine)}, so ${american(hrUnderPrice)} cannot be compared. Paper only until one is.`;
  } else if (blocker === "qb_out") {
    action = "Starting QB out — recheck. Our number does not know about it.";
  } else if (blocker === "early_season") {
    const at = hrUnderPrice !== null ? ` at ${american(hrUnderPrice)}` : "";
    const n = minGamesPlayed ?? 0;
    action = `Paper only — ${n} game${n === 1 ? "" : "s"} played this season; real money needs ${MIN_GAMES_FOR_REAL_MONEY}. Everything else clears: first-half under ${fmt(hrLine)}${at} on Hard Rock.`;
  } else if (tier === "EDGE") {
    action = `Not yet — the line is ${fmt(gap ?? 0)} above our number. It becomes a bet at ${fmt(killLine)} or higher.`;
  } else {
    const gg = gap ?? 0;
    action =
      gg > 0
        ? `Pass: the line is ${fmt(gg)} above our number. It needs ${fmt(killLine)} or higher.`
        : `Pass: the line is ${fmt(Math.abs(gg))} below our number, so this leans over. We only bet unders.`;
  }

  return {
    score,
    tier,
    blocker,
    action,
    gap,
    lineBasis,
    killLine,
    killPrice,
    verdict,
    reason,
    hrGap,
    inBand,
    offMarket,
    pricePos,
    priceLine: priceSentence({ hrLine, hrUnderPrice, ev, evVerdict }),
    input: {
      hrLine,
      hrUnderPrice,
      ev,
      evVerdict,
      marketLine,
      fallbackLine,
      marketFairUnder,
      hrCentred,
      minGamesPlayed,
      bestLine: check ? check.best : null,
    },
  };
}

/** predictions.line_used for the model row: Hard Rock's line at scoring (its first capture), else the books', else the reference. */
export function lineUsedFor(g) {
  if (g.hr && g.hr.length) return g.hr[0].line;
  const bookLines = Object.values(g.books).map(([line]) => line);
  if (bookLines.length) return median(bookLines);
  return g.ref;
}

// --- lib/homeBoard.ts: sorting, ranks, counts ------------------------------

const ms = (g) => g.kick.getTime();

export function sortGames(rows) {
  return [...rows].sort(
    (a, b) =>
      Number(a.kickedOff) - Number(b.kickedOff) ||
      b.edge.score - a.edge.score ||
      (b.edge.gap ?? Number.NEGATIVE_INFINITY) -
        (a.edge.gap ?? Number.NEGATIVE_INFINITY) ||
      ms(a.game) - ms(b.game) ||
      a.game.away.localeCompare(b.game.away),
  );
}

export function assignCapRanks(rows, held, cap = WEEKLY_BET_CAP) {
  const bets = rows.filter((r) => r.edge.tier === "BET" && !r.kickedOff);
  const ranked = [...bets].sort(
    (a, b) =>
      Number(!held.has(a.game.id)) - Number(!held.has(b.game.id)) ||
      (b.edge.gap ?? Number.NEGATIVE_INFINITY) -
        (a.edge.gap ?? Number.NEGATIVE_INFINITY) ||
      (b.edge.input.ev ?? Number.NEGATIVE_INFINITY) -
        (a.edge.input.ev ?? Number.NEGATIVE_INFINITY) ||
      ms(a.game) - ms(b.game) ||
      a.game.away.localeCompare(b.game.away),
  );
  const rank = new Map(ranked.map((r, i) => [r.game.id, i + 1]));
  return rows.map((r) => {
    const cr = rank.get(r.game.id) ?? null;
    return { ...r, capRank: cr, overCap: cr !== null && cr > cap };
  });
}

// --- lib/answerBar.ts ---------------------------------------------------------

export function shortNeed(action) {
  const i = action.toLowerCase().lastIndexOf("needs ");
  if (i < 0) return action;
  return action.slice(i).replace(/\.\s*$/, "");
}

function numbersOf(r) {
  const line = r.check ? r.check.hrLine : null;
  if (line === null) return "no line yet";
  const price = r.check ? r.check.hrUnderPrice : null;
  return `u${fmt(line)}${price === null ? "" : ` ${american(price)}`}`;
}

// --- lib/cronJobs.ts + lib/boardHealth.ts::lastClosedSlot ------------------

const DAY_ORDER = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const PM = { openMin: 15 * 60 + 45, closeMin: 17 * 60 + 15 };
export const CRON_JOBS = {
  "card-tue-pm": { days: ["Tue"], ...PM, slot: "tue_pm" },
  "card-thu-pm": { days: ["Thu"], ...PM, slot: "thu_pm" },
  "card-fri-pm": { days: ["Fri"], ...PM, slot: "fri_pm" },
  "card-sat-am": {
    days: ["Sat"],
    openMin: 7 * 60,
    closeMin: 8 * 60 + 15,
    slot: "sat_am",
  },
  sunday: { days: ["Sun"], openMin: 13 * 60, closeMin: 17 * 60 },
  grade: { days: null, openMin: 0, closeMin: 24 * 60 - 1 },
};

/** Of these ET day/minute windows, the one that closed most recently at or before `now`. */
export function lastClosedSlot(slots, now) {
  const nowMin = etMinutesOfDay(now);
  const nowDow = DAY_ORDER.indexOf(etParts(now).weekday);
  let best = null;
  for (const s of slots) {
    const dow = DAY_ORDER.indexOf(s.day);
    let ago = (nowDow - dow) * 1440 + (nowMin - s.closeMin);
    if (ago < 0) ago += 7 * 1440;
    const openedAt = new Date(
      now.getTime() - (ago + (s.closeMin - s.openMin)) * 60_000,
    );
    if (best === null || ago < best.agoMin)
      best = { ...s, openedAt, agoMin: ago };
  }
  return best;
}

/** The most recently closed CARD build window: its slot name and open instant. */
export function lastClosedCardSlot(now) {
  const slots = Object.values(CRON_JOBS)
    .filter((j) => j.slot)
    .map((j) => ({
      day: j.days[0],
      openMin: j.openMin,
      closeMin: j.closeMin,
      slot: j.slot,
    }));
  return lastClosedSlot(slots, now);
}

/** The scheduled Neon-writing jobs that end with a health contract
 *  (beatvegas/health.py CONTRACTS; lib/boardHealth.ts HEALTH_JOB_IDS). */
export const HEALTH_JOBS = ["card", "grade", "sunday", "lines_watch"];

/** For every cron job: an instant five minutes into its last closed window -- a tick that acted in time, so opsWarnings stays silent. */
export function lastDispatchTicks(now) {
  const out = {};
  for (const [id, job] of Object.entries(CRON_JOBS)) {
    const days = job.days ?? DAY_ORDER;
    const win = lastClosedSlot(
      days.map((day) => ({
        day,
        openMin: job.openMin,
        closeMin: job.closeMin,
      })),
      now,
    );
    out[id] = new Date(win.openedAt.getTime() + 5 * 60_000);
  }
  return out;
}

// --- card.py display chips --------------------------------------------------

const KEY_NUMBERS_1H = [24.0, 28.0, 31.0];
export function totalBand(total) {
  if (total == null) return null;
  if (total < 45) return "<45";
  if (total < 52) return "45–52";
  if (total < 60) return "52–60";
  return "60+";
}
export function hookSide(line) {
  if (line == null) return null;
  for (const k of KEY_NUMBERS_1H) {
    if (Math.abs(line - k) < 1e-9) return "on_key";
    if (Math.abs(line - k - 0.5) < 1e-9) return "key+0.5";
    if (Math.abs(k - line - 0.5) < 1e-9) return "key−0.5";
  }
  return "other";
}
export const keyDist = (line) =>
  line == null
    ? null
    : Math.min(...KEY_NUMBERS_1H.map((k) => Math.abs(line - k)));

/** ISO-8601 UTC with a Z and no milliseconds -- the shape card.py::_iso writes. */
export const isoZ = (d) => d.toISOString().replace(/\.\d{3}Z$/, "Z");

// --- the expectations -------------------------------------------------------

/**
 * Everything a spec asserts, derived from the week. `picked` is the set of
 * game ids with a real-money 1H ticket this season (the fixture's one pending
 * ticket on 900001 plus the two graded last-week tickets); `paperLogged` the
 * ids the card paper-logged this week.
 */
export function buildExpected(week) {
  const { now, games } = week;
  const thisWeek = games.filter((g) => g.week === week.week);
  const upcoming = thisWeek.filter((g) => g.kick.getTime() > now.getTime());
  const checks = new Map(thisWeek.map((g) => [g.id, lineCheckFor(g)]));
  const cons = new Map(thisWeek.map((g) => [g.id, consensusFor(g)]));

  // H-PCT. The BOARD reads the bar over every row of the week (played rows
  // included -- lib/homeBoard.ts maps `rows`); the CARD over the games still
  // to kick off (card.py `upcoming`). Both must land on the same number here.
  const slateGapsOf = (list) =>
    list
      .map((g) => {
        const c = checks.get(g.id);
        if (!c || c.hrLine === null || c.hrCentred === false) return null;
        return round2(c.hrLine - g.bv);
      })
      .filter((x) => x !== null);
  const boardGaps = slateGapsOf(thisWeek);
  const cardGaps = slateGapsOf(upcoming);
  const bar = slateBar(boardGaps);
  const cardBar = slateBar(cardGaps);
  if (bar === null || cardBar !== bar) {
    throw new Error(`fixture bar mismatch: board ${bar} vs card ${cardBar}`);
  }
  const slate = { bar, n: boardGaps.length, share: PCT_SHARE, basis: "slate" };

  const pickedIds = new Set([900001, 900013, 900014]);
  const paperLogged = new Set([900003, 900004]);

  let rows = thisWeek.map((g) => {
    const check = checks.get(g.id);
    const edge = edgeFor(g, bar, check, cons.get(g.id));
    return {
      game: g,
      check,
      cons: cons.get(g.id),
      edge,
      kickedOff: g.kick.getTime() <= now.getTime(),
      picked: pickedIds.has(g.id),
      capRank: null,
      overCap: false,
      boardRank: null,
    };
  });
  rows = assignCapRanks(sortGames(rows), pickedIds);
  let n = 0;
  rows = rows.map((r) => (r.kickedOff ? r : { ...r, boardRank: ++n }));

  const counts = {
    bet: rows.filter((r) => r.edge.tier === "BET").length,
    edge: rows.filter((r) => r.edge.tier === "EDGE").length,
    pass: rows.filter((r) => r.edge.tier === "PASS").length,
  };
  const clearing = rows.filter(
    (r) =>
      r.edge.lineBasis === "hardrock" &&
      r.edge.gap !== null &&
      r.edge.gap > 0 &&
      r.edge.gap >= bar &&
      (r.check ? r.check.hrCentred : null) !== false,
  ).length;
  const barLine = `This week’s bar: ${bar.toFixed(2)} pts — the gap of the top ${Math.round(100 * slate.share)}% of ${slate.n} priced games; ${clearing} clear it. A game must also pass the price, market and news gates to be a bet.`;

  // lib/answerBar.ts::buildAnswer
  const live = rows.filter((r) => !r.kickedOff);
  const byRank = (a, b) =>
    (a.boardRank ?? Infinity) - (b.boardRank ?? Infinity);
  const answerBets = live
    .filter((r) => r.edge.tier === "BET")
    .sort((a, b) => Number(a.picked) - Number(b.picked) || byRank(a, b))
    .map((r) => ({
      gameId: r.game.id,
      matchup: `${r.game.away} @ ${r.game.home}`,
      numbers: numbersOf(r),
      picked: r.picked,
    }));
  const closest = live
    .filter((r) => r.edge.tier !== "BET")
    .sort(byRank)
    .slice(0, 3)
    .map((r) => ({
      gameId: r.game.id,
      matchup: `${r.game.away} @ ${r.game.home}`,
      numbers: numbersOf(r),
      needs: shortNeed(r.edge.action),
    }));
  const open = answerBets.filter((b) => !b.picked).length;
  const placed = answerBets.length - open;
  const usedSlots = 1; // real, non-bonus 1H tickets logged on this week: 900001
  const answer = {
    bets: answerBets,
    open,
    closest,
    used: usedSlots,
    cap: WEEKLY_BET_CAP,
    headline:
      open > 0
        ? `${open} ${open === 1 ? "bet" : "bets"} live`
        : placed > 0
          ? `${placed} ${placed === 1 ? "bet" : "bets"} placed, nothing else live`
          : "No bets yet this week",
    slotsLine: `${usedSlots} of ${WEEKLY_BET_CAP} slots used`,
  };

  // --- the card (beatvegas/card.py::build_card), built ten minutes ago ---
  const builtAt = new Date(now.getTime() - 10 * 60_000);
  const slotWin = lastClosedCardSlot(now);
  const cardRows = rows.filter((r) => upcoming.some((g) => g.id === r.game.id));
  const TIER_ORDER = { BET: 0, EDGE: 1, PASS: 2 };
  const sortKey = (r) => [
    TIER_ORDER[r.edge.tier],
    -(r.edge.gap ?? -Infinity),
    -(r.edge.input.ev ?? -Infinity),
    isoZ(r.game.kick),
    r.game.away,
  ];
  const cmp = (a, b) => {
    const ka = sortKey(a);
    const kb = sortKey(b);
    for (let i = 0; i < ka.length; i++) {
      if (ka[i] < kb[i]) return -1;
      if (ka[i] > kb[i]) return 1;
    }
    return 0;
  };
  const items = [...cardRows].sort(cmp).map((r) => {
    const g = r.game;
    const e = r.edge;
    const c = r.check;
    const byBook = latestByBook(g);
    const others = median(
      [...byBook.entries()].filter(([k]) => k !== HR).map(([, o]) => o.line),
    );
    const hrLine = e.input.hrLine;
    const hrVsMarket =
      hrLine !== null && others !== null ? round2(hrLine - others) : null;
    const hrOpen = g.hr && g.hr.length ? g.hr[0].line : null;
    const paperBlocker = e.inBand
      ? e.offMarket
        ? "off_market"
        : e.input.ev === null
          ? "no_fair_price"
          : e.input.ev < BET_MIN_EV
            ? "price"
            : null
      : null;
    const why = [
      gapSentence(g.bv, hrLine, e.input.marketLine, g.ref, e.gap),
      e.priceLine,
    ];
    if (
      hrLine !== null &&
      hrOpen !== null &&
      Math.abs(hrOpen - hrLine) >= 0.05
    ) {
      why.push(
        `Hard Rock opened at ${fmt(hrOpen)} and has moved ${hrLine > hrOpen ? "up" : "down"} to ${fmt(hrLine)}.`,
      );
    }
    if (hrVsMarket !== null && Math.abs(hrVsMarket) >= 0.05) {
      why.push(
        `Hard Rock’s ${fmt(hrLine)} is ${fmt(Math.abs(hrVsMarket))} points ${hrVsMarket > 0 ? "above" : "below"} the other books’ median (${fmt(hrLine - hrVsMarket)}) — a ${hrVsMarket > 0 ? "better" : "worse"} number for an under.`,
      );
    }
    return {
      game_id: g.id,
      away: g.away,
      home: g.home,
      kick: isoZ(g.kick),
      tier: e.tier,
      blocker: e.blocker,
      hr_line: hrLine,
      hr_price: e.input.hrUnderPrice,
      hr_open: hrOpen,
      market_line: e.input.marketLine,
      fair_under:
        e.input.marketFairUnder === null
          ? null
          : Math.round(e.input.marketFairUnder * 1e4) / 1e4,
      fair_source: e.input.marketFairUnder === null ? null : "books",
      hr_vs_market: hrVsMarket,
      ev: e.input.ev === null ? null : Math.round(e.input.ev * 1e4) / 1e4,
      bv_line: round2(g.bv),
      under_score: g.underScore,
      games_played: e.input.minGamesPlayed,
      qb_out: false,
      qb_out_detail: null,
      gap: e.gap,
      gap_basis: e.lineBasis,
      kill_line: e.killLine,
      kill_price: e.killPrice,
      action: e.action,
      why,
      paper_logged: paperLogged.has(g.id),
      qualifies: e.inBand,
      bar: round2(bar),
      hr_centred: c ? c.hrCentred : false,
      paper_blocker: paperBlocker,
      cap_rank: r.capRank,
      over_cap: r.overCap,
      degraded_inputs: [],
      gate_blocker: null,
      full_game_total: g.fg.total,
      spread: g.fg.spread,
      total_band: totalBand(g.fg.total),
      hook_side: hookSide(hrLine),
      key_dist: keyDist(hrLine),
    };
  });
  const card = {
    season: week.season,
    week: week.week,
    built_at: isoZ(builtAt),
    model_read: true,
    slot: slotWin.slot,
    status: "final",
    degraded: [],
    counts: {
      bet: items.filter((i) => i.tier === "BET" && !i.over_cap).length,
      edge: items.filter((i) => i.tier === "EDGE").length,
      pass: items.filter((i) => i.tier === "PASS").length,
      over_cap: items.filter((i) => i.over_cap).length,
      degraded: 0,
    },
    paper: {
      qualifying: items.filter((i) => i.qualifies).length,
      over_cap: items.filter((i) => i.over_cap).length,
      cap: WEEKLY_BET_CAP,
    },
    slate: {
      bar: round2(bar),
      n: cardGaps.length,
      share: PCT_SHARE,
      basis: "slate",
    },
    items,
    notes: [],
  };

  // --- the ledger (manual_picks), by scenario -----------------------------
  const byId = new Map(rows.map((r) => [r.game.id, r]));
  const g13 = games.find((g) => g.id === 900013);
  const g14 = games.find((g) => g.id === 900014);
  const g1 = byId.get(900001);
  const g3 = byId.get(900003);
  const g4 = byId.get(900004);
  const unit = round2(100 / 110); // +0.91 on a -110 winner
  const picks = [
    {
      id: 1,
      game: g13,
      week: week.prevWeek,
      line: 45.5,
      price: -110,
      isPaper: false,
      verdict: "BET",
      reason: "model_gap",
      gap: round2(45.5 - g13.bv),
      ev: -0.0455,
      hrLine: 45.5,
      modelLine: g13.bv,
      modelScore: g13.underScore,
      graded: true,
      actualFh: 38,
      result: "under",
      units: unit,
      openingLine: 46.0,
      closingLine: 44.5,
      closingPrice: -112,
      clv: -1.0, // closing - bet: the line FELL after the bet -> favourable
      clvProb: 0.012,
      blocker: null,
      note: "slow pace, both defenses top-25",
      placedAt: new Date(g13.kick.getTime() - 20 * 3_600_000),
      scenario: "real, WON",
    },
    {
      id: 2,
      game: g14,
      week: week.prevWeek,
      line: 52.5,
      price: -115,
      isPaper: false,
      verdict: "BET",
      reason: "model_gap",
      gap: round2(52.5 - g14.bv),
      ev: -0.0478,
      hrLine: 52.5,
      modelLine: g14.bv,
      modelScore: g14.underScore,
      graded: true,
      actualFh: 58,
      result: "over",
      units: -1.0,
      openingLine: 52.0,
      closingLine: 53.0,
      closingPrice: -110,
      clv: 0.5, // the line ROSE after the bet -> unfavourable
      clvProb: -0.006,
      blocker: null,
      note: null,
      placedAt: new Date(g14.kick.getTime() - 18 * 3_600_000),
      scenario: "real, LOST",
    },
    {
      id: 3,
      game: g1.game,
      week: week.week,
      line: 44.0,
      price: -110,
      isPaper: false,
      verdict: "BET",
      reason: g1.edge.reason,
      gap: g1.edge.hrGap,
      ev: Math.round(g1.edge.input.ev * 1e4) / 1e4,
      hrLine: 44.0,
      modelLine: g1.game.bv,
      modelScore: g1.game.underScore,
      graded: false,
      blocker: null,
      note: "the Saturday noon game",
      placedAt: new Date(now.getTime() - 20 * 3_600_000),
      scenario: "real, pending, on BET #1",
    },
    {
      id: 4,
      game: g3.game,
      week: week.week,
      line: 47.5,
      price: -135,
      isPaper: true,
      verdict: "WATCH",
      reason: g3.edge.reason,
      gap: g3.edge.hrGap,
      ev: Math.round(g3.edge.input.ev * 1e4) / 1e4,
      hrLine: 47.5,
      modelLine: g3.game.bv,
      modelScore: g3.game.underScore,
      graded: false,
      blocker: "price",
      note: null,
      placedAt: builtAt,
      scenario: "paper, blocked by price",
    },
    {
      id: 5,
      game: g4.game,
      week: week.week,
      line: 44.5,
      price: -110,
      isPaper: true,
      verdict: "WATCH",
      reason: g4.edge.reason,
      gap: g4.edge.hrGap,
      ev: null,
      hrLine: 44.5,
      modelLine: g4.game.bv,
      modelScore: g4.game.underScore,
      graded: false,
      blocker: "off_market",
      note: null,
      placedAt: builtAt,
      scenario: "paper, blocked off_market",
    },
    {
      id: 6,
      game: g13,
      week: week.prevWeek,
      line: 45.5,
      price: -110,
      isPaper: true,
      verdict: "BET",
      reason: "model_gap",
      gap: round2(45.5 - g13.bv),
      ev: -0.0455,
      hrLine: 45.5,
      modelLine: g13.bv,
      modelScore: g13.underScore,
      graded: true,
      actualFh: 38,
      result: "under",
      units: unit,
      openingLine: 46.0,
      closingLine: 44.5,
      closingPrice: -112,
      clv: -1.0,
      clvProb: 0.012,
      blocker: "cap",
      note: null,
      placedAt: new Date(g13.kick.getTime() - 40 * 3_600_000),
      scenario: "paper, sixth BET by gap that week (cap)",
    },
  ];

  const ledger = {
    // lib/record.ts::recordFrom over the graded real 1H picks
    real: {
      record: "1-1",
      units: `${unit - 1.0 >= 0 ? "+" : ""}${(unit - 1.0).toFixed(2)}`,
      n: 2,
    },
    // ...and the graded paper picks
    paper: { record: "1-0", units: `+${unit.toFixed(2)}`, n: 1, hit: "100.0%" },
    realBets: 3,
    paperPicks: 3,
    // lib/decision-quality.ts::clvSummary on the two graded real picks:
    // stored clv -1.0 and +0.5 -> displayed (negated) +1.00 and -0.50.
    clvDisplayed: ["+1.00", "-0.50"],
    avgPointsGained: "+0.25",
    pctFavourable: "50.0%",
    startUsd: 100,
    unitUsd: 10,
    bankrollUsd: Math.round((100 + (unit - 1.0) * 10) * 100) / 100,
  };

  return {
    slate,
    bar,
    counts,
    clearing,
    barLine,
    rows,
    rankOrder: rows.filter((r) => !r.kickedOff).map((r) => r.game.id),
    playedIds: rows.filter((r) => r.kickedOff).map((r) => r.game.id),
    betIds: rows
      .filter((r) => r.edge.tier === "BET" && !r.kickedOff)
      .map((r) => r.game.id),
    answer,
    card,
    builtAt,
    picks,
    pickedIds,
    paperLogged,
    ledger,
    lastDispatch: lastDispatchTicks(now),
    // lib/boardHealth.ts::gaugesFrom: value = the verdict, note = the run.
    // Every job wrote `ok` from its last run, at the instant its window closed.
    health: Object.fromEntries(
      HEALTH_JOBS.map((job, i) => {
        const at = new Date(now.getTime() - (i + 1) * 3_600_000);
        at.setUTCMinutes(0, 0, 0);
        const slot = job === "card" ? ` slot=${slotWin.slot}` : "";
        return [
          job,
          {
            verdict: "ok",
            at,
            note: `run=3587000000${i + 1} event=schedule${slot} info=e2e=fixture`,
          },
        ];
      }),
    ),
  };
}
