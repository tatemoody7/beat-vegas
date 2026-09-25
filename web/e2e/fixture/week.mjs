// The synthetic week the e2e lane runs against: fourteen fictional games, laid
// out RELATIVE TO NOW so every wall-clock rule in the app (lib/week.ts
// defaultWeek, boardHealth.staleness/buildStatus, nextBuild, GameRow.kickedOff,
// the dispatch gauges) sees a live season whenever the suite runs.
//
// Layout: twelve upcoming games (900001-900011, 900015) on the Thursday, Friday and
// Saturday of the first weekend whose Thursday evening is at least twelve hours
// away, one game played three days ago in the same week (900012), and two
// played ten days ago in the previous week (900013-900014) so the real-money
// ledger has a graded win and a graded loss to show. Every kickoff is an ET
// wall time turned into an instant, so the day headings come out Thu / Fri /
// Sat whatever the machine's zone.
//
// Nothing here is real: 23 made-up programs plus one of the four MY_TEAMS names
// (lib/homeBoard.ts) so the "My teams" filter has one row to show. Team ids are
// far outside CFBD's range, so no vendored logo ever matches.
//
// Every timestamp exported here is a Date (an instant). seed.mjs writes them as
// naive UTC, the convention every timestamp column in the schema follows.

export const ET_ZONE = "America/New_York";

const ET_FMT = new Intl.DateTimeFormat("en-US", {
  timeZone: ET_ZONE,
  weekday: "short",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/** The ET wall-clock pieces of an instant (mirrors lib/et.ts::etParts). */
export function etParts(d) {
  const parts = ET_FMT.formatToParts(d);
  const get = (type) => parts.find((p) => p.type === type)?.value ?? "";
  return {
    weekday: get("weekday").slice(0, 3),
    year: Number(get("year")),
    month: Number(get("month")),
    day: Number(get("day")),
    hour: Number(get("hour")) % 24,
    minute: Number(get("minute")),
  };
}

/** Minutes since ET midnight (lib/et.ts::etMinutesOfDay). */
export function etMinutesOfDay(d) {
  const p = etParts(d);
  return p.hour * 60 + p.minute;
}

/**
 * The instant at which the ET wall clock reads y-m-d h:mi. Two correction
 * passes handle the DST offset without any zone arithmetic of our own.
 */
export function etInstant(y, m, d, h, mi) {
  let t = Date.UTC(y, m - 1, d, h, mi);
  for (let i = 0; i < 2; i++) {
    const p = etParts(new Date(t));
    const want = Date.UTC(y, m - 1, d, h, mi);
    const got = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute);
    t += want - got;
  }
  return new Date(t);
}

/** The ET calendar date `n` days after (y, m, d). */
function addDays(y, m, d, n) {
  const p = etParts(new Date(Date.UTC(y, m - 1, d + n, 17)));
  return { y: p.year, m: p.month, d: p.day, weekday: p.weekday };
}

/** CFB season for an instant (lib/season.ts::currentCfbSeason). */
export function currentCfbSeason(now) {
  return now.getUTCMonth() + 1 >= 6
    ? now.getUTCFullYear()
    : now.getUTCFullYear() - 1;
}

/**
 * The anchor Saturday: the first one whose Thursday 19:00 ET is at least
 * MIN_LEAD_H hours from now, so every upcoming game is still upcoming when the
 * suite runs, and the previous Saturday's slate is fully played.
 */
export const MIN_LEAD_H = 12;

export function anchorSaturday(now) {
  const today = etParts(now);
  for (let n = 0; n < 14; n++) {
    const day = addDays(today.year, today.month, today.day, n);
    if (day.weekday !== "Sat") continue;
    const thu = addDays(day.y, day.m, day.d, -2);
    const thuEvening = etInstant(thu.y, thu.m, thu.d, 19, 0);
    if (thuEvening.getTime() >= now.getTime() + MIN_LEAD_H * 3_600_000) {
      return day;
    }
  }
  throw new Error("no anchor Saturday found in the next two weeks");
}

/** Whole-hour instant `hours` before now (so a re-seed minutes later lands on the same row values). */
function hoursAgo(now, hours) {
  const t = new Date(now.getTime() - hours * 3_600_000);
  t.setUTCMinutes(0, 0, 0);
  return t;
}

export const WEEK = 5;
export const PREV_WEEK = 4;

/** Team ids start here; nothing in web/data/team_logos.json is anywhere near. */
const TEAM_BASE = 990000;

export const TEAM_NAMES = [
  "Aldercrest",
  "Bayview State",
  "Cedar Ridge",
  "Dunmore Tech",
  "Eastbrook",
  "Fairhaven",
  "Granite Falls",
  "Harrowgate",
  "Ironwood",
  "Juniper Valley",
  "Kestrel Point",
  "Lakemont",
  "Marrow Hill",
  "Northgate",
  "Oakhurst",
  "Pinecrest",
  "Quarry Bend",
  "Ridgeline",
  "Silverlake",
  "Thornbury",
  "Umberfield",
  "Vale City",
  "Westmark",
  // The one real name: lib/homeBoard.ts MY_TEAMS, so ?mine=1 has a row.
  "Kansas State",
  // Appended (2026-09-25) so earlier ids stay put: the alternate-line game.
  "Yarrow Glen",
  "Zephyr Bay",
];

export const TEAMS = TEAM_NAMES.map((school, i) => ({
  id: TEAM_BASE + i + 1,
  school,
  conference: i % 2 === 0 ? "Coastal" : "Highland",
}));

export const TEAM_ID = Object.fromEntries(TEAMS.map((t) => [t.school, t.id]));

/** Two-way quotes at a book: `[line, overPrice, underPrice]`. */
const std = (line) => [line, -110, -110];

/**
 * Build the week. `now` is the seed instant; everything hangs off it.
 *
 * Each game carries:
 *   id, away, home, kick (Date), bv (our number), underScore, hr (Hard Rock's
 *   1H captures oldest -> newest, or null), books ({draftkings, fanduel,
 *   betmgm} latest 1H quotes, or {}), fg {total, spread, over, under}, ref (the
 *   derived reference line), played {homePts, awayPts, homeFh, awayFh} or null,
 *   week, scenario (what the row is for, in words), factors extras.
 */
export function buildWeek(now = new Date()) {
  const sat = anchorSaturday(now);
  const fri = addDays(sat.y, sat.m, sat.d, -1);
  const thu = addDays(sat.y, sat.m, sat.d, -2);
  const at = (day, h, mi) => etInstant(day.y, day.m, day.d, h, mi);
  const season = currentCfbSeason(now);

  // Capture instants for the upcoming games: an early sweep and a late one.
  const cap1 = hoursAgo(now, 72);
  const cap2 = hoursAgo(now, 24);
  // The played game (900012) kicked off three days ago; its captures precede it.
  const playedKick = hoursAgo(now, 72);
  const playedCap1 = hoursAgo(now, 120);
  const playedCap2 = hoursAgo(now, 75);
  // Last week's two games.
  const prevKick = hoursAgo(now, 240);
  const prevKick2 = hoursAgo(now, 237);
  const prevCap1 = hoursAgo(now, 288);
  const prevCap2 = hoursAgo(now, 243);

  const hrRow = (t, line, over = -110, under = -110) => ({
    capturedAt: t,
    line,
    over,
    under,
  });

  const games = [
    {
      id: 900001,
      away: "Aldercrest",
      home: "Bayview State",
      kick: at(sat, 12, 0),
      bv: 40.0,
      underScore: 74,
      hr: [hrRow(cap1, 43.5), hrRow(cap2, 44.0)],
      books: {
        draftkings: std(44.0),
        fanduel: [44.0, -112, -108],
        betmgm: std(44.0),
      },
      fg: { total: 55.5, spread: -7.5 },
      ref: 27.5,
      scenario: "BET #1 (gap 4.0), real ticket already logged",
    },
    {
      id: 900002,
      away: "Cedar Ridge",
      home: "Dunmore Tech",
      kick: at(thu, 19, 30),
      bv: 50.0,
      underScore: 71,
      hr: [hrRow(cap1, 53.0), hrRow(cap2, 53.5)],
      books: {
        draftkings: std(53.5),
        fanduel: std(53.5),
        betmgm: std(53.5),
      },
      fg: { total: 66.5, spread: -3.5 },
      ref: 33.0,
      scenario: "BET #2 (gap 3.5, sets the bar), open",
    },
    {
      id: 900003,
      away: "Eastbrook",
      home: "Fairhaven",
      kick: at(fri, 19, 0),
      bv: 44.0,
      underScore: 69,
      hr: [hrRow(cap1, 47.0, 105, -135), hrRow(cap2, 47.5, 105, -135)],
      books: {
        draftkings: std(47.5),
        fanduel: std(47.5),
        betmgm: std(47.5),
      },
      fg: { total: 59.5, spread: -10.5 },
      ref: 29.5,
      scenario: "EDGE blocked by price (-135), paper pick",
    },
    {
      id: 900004,
      away: "Granite Falls",
      home: "Harrowgate",
      kick: at(sat, 15, 30),
      bv: 41.0,
      underScore: 68,
      hr: [hrRow(cap1, 44.5), hrRow(cap2, 44.5)],
      books: {
        draftkings: std(45.5),
        fanduel: std(45.5),
        betmgm: std(45.5),
      },
      fg: { total: 56.5, spread: -14.5 },
      ref: 28.0,
      scenario: "EDGE blocked off_market (HR 1.0 below the market), paper pick",
    },
    {
      id: 900005,
      away: "Kansas State",
      home: "Ironwood",
      kick: at(sat, 19, 0),
      bv: 49.5,
      underScore: 62,
      hr: [hrRow(cap1, 51.5), hrRow(cap2, 51.5)],
      books: {
        draftkings: std(51.5),
        fanduel: std(51.5),
        betmgm: std(51.5),
      },
      fg: { total: 63.5, spread: -6.5 },
      ref: 31.5,
      scenario: "EDGE, gap 2.0 short of the bar (blocker gap); a MY_TEAMS row",
    },
    {
      id: 900006,
      away: "Juniper Valley",
      home: "Lakemont",
      kick: at(thu, 20, 0),
      bv: 45.9,
      underScore: 55,
      hr: [hrRow(cap1, 46.5), hrRow(cap2, 46.5)],
      books: {
        draftkings: std(46.5),
        fanduel: std(46.5),
        betmgm: std(46.5),
      },
      fg: { total: 58.5, spread: -2.5 },
      ref: 29.0,
      scenario: "PASS, gap 0.6",
    },
    {
      id: 900007,
      away: "Marrow Hill",
      home: "Northgate",
      kick: at(sat, 19, 30),
      bv: 55.0,
      underScore: 38,
      hr: [hrRow(cap1, 54.5), hrRow(cap2, 54.0)],
      books: {
        draftkings: std(54.0),
        fanduel: std(54.0),
        betmgm: std(54.0),
      },
      fg: { total: 71.5, spread: -1.5 },
      ref: 35.5,
      scenario: "PASS, leans over (gap -1.0)",
    },
    {
      id: 900008,
      away: "Oakhurst",
      home: "Pinecrest",
      kick: at(sat, 22, 30),
      bv: 38.2,
      underScore: 57,
      hr: [hrRow(cap1, 39.0), hrRow(cap2, 39.0)],
      books: {
        draftkings: std(39.0),
        fanduel: std(39.0),
        betmgm: std(39.0),
      },
      fg: { total: 48.5, spread: -20.5 },
      ref: 24.5,
      scenario: "PASS, gap 0.8 (score 54, one under the amber band)",
    },
    {
      id: 900009,
      away: "Quarry Bend",
      home: "Ridgeline",
      kick: at(fri, 21, 0),
      bv: 48.5,
      underScore: 50,
      hr: [hrRow(cap1, 48.5, -105, -115), hrRow(cap2, 48.5, -105, -115)],
      books: {
        draftkings: std(48.5),
        fanduel: std(48.5),
        betmgm: std(48.5),
      },
      fg: { total: 61.5, spread: -4.5 },
      ref: 30.5,
      scenario: "PASS, right on our number",
    },
    {
      id: 900015,
      away: "Yarrow Glen",
      home: "Zephyr Bay",
      kick: at(sat, 15, 30),
      bv: 44.0,
      underScore: 70,
      // The late sweep's Hard Rock quote is an ALTERNATE line (3 pts off every
      // other book at -160, the Texas @ Tennessee shape of 2026-09-25).
      hr: [hrRow(cap1, 47.5), hrRow(cap2, 50.5, 125, -160)],
      books: {
        draftkings: std(47.5),
        fanduel: std(47.5),
        betmgm: std(47.5),
      },
      fg: { total: 58.5, spread: -6.5 },
      ref: 29.0,
      scenario:
        "EDGE hr_alt_line: the feed's newest Hard Rock quote is an alternate; the board shows the last main line (47.5) with its time; never a bet",
    },
    {
      id: 900010,
      away: "Silverlake",
      home: "Thornbury",
      kick: at(fri, 20, 30),
      bv: 42.2,
      underScore: 52,
      hr: null,
      books: { draftkings: std(42.5), fanduel: std(42.5) },
      fg: { total: 54.5, spread: -9.5 },
      ref: 27.0,
      scenario: "no Hard Rock line; market basis, PASS",
    },
    {
      id: 900011,
      away: "Umberfield",
      home: "Vale City",
      kick: at(sat, 16, 0),
      bv: 47.6,
      underScore: 53,
      hr: null,
      books: {},
      fg: { total: 62.5, spread: -5.5 },
      ref: 48.0,
      scenario: "no first-half line anywhere; reference basis, PASS",
    },
    {
      id: 900012,
      away: "Kestrel Point",
      home: "Westmark",
      kick: playedKick,
      bv: 30.0,
      underScore: 52,
      hr: [hrRow(playedCap1, 31.0), hrRow(playedCap2, 30.5)],
      books: {
        draftkings: std(30.5),
        fanduel: std(30.5),
        betmgm: std(30.5),
      },
      fg: { total: 51.5, spread: 3.5 },
      ref: 25.5,
      played: { homePts: 24, awayPts: 27, homeFh: 10, awayFh: 17 },
      scenario: "played three days ago, this week; under won at 30.5",
    },
    {
      id: 900013,
      away: "Harrowgate",
      home: "Eastbrook",
      kick: prevKick,
      week: PREV_WEEK,
      bv: 41.9,
      underScore: 72,
      hr: [hrRow(prevCap1, 46.0), hrRow(prevCap2, 45.5)],
      books: { draftkings: std(44.5), fanduel: std(44.5) },
      fg: { total: 52.5, spread: -6.5 },
      ref: 26.0,
      played: { homePts: 24, awayPts: 21, homeFh: 21, awayFh: 17 },
      scenario:
        "last week; real ticket WON (u45.5, first half 38), paper 'cap' pick",
    },
    {
      id: 900014,
      away: "Thornbury",
      home: "Kestrel Point",
      kick: prevKick2,
      week: PREV_WEEK,
      bv: 49.0,
      underScore: 70,
      hr: [
        hrRow(prevCap1, 52.0, -105, -115),
        hrRow(prevCap2, 52.5, -105, -115),
      ],
      books: { draftkings: std(53.0), fanduel: std(53.0) },
      fg: { total: 60.5, spread: -2.5 },
      ref: 30.0,
      played: { homePts: 35, awayPts: 31, homeFh: 31, awayFh: 27 },
      scenario: "last week; real ticket LOST (u52.5, first half 58)",
    },
  ].map((g) => ({
    ...g,
    week: g.week ?? WEEK,
    season,
    played: g.played ?? null,
    awayTeamId: TEAM_ID[g.away],
    homeTeamId: TEAM_ID[g.home],
    // Games played this season by each side: comfortably past the
    // MIN_GAMES_FOR_REAL_MONEY = 2 gate, so early_season never fires here.
    gamesPlayed: { home: 4, away: 4 },
    // The model row was written before kickoff (records.ts::scoredAfter).
    scoredAt: hoursAgo(now, g.week === WEEK ? 96 : 264),
  }));

  return {
    now,
    season,
    week: WEEK,
    prevWeek: PREV_WEEK,
    anchor: { thu, fri, sat },
    games,
    teams: TEAMS,
    captures: { cap1, cap2 },
  };
}

export const HR = "hardrockbet";
export const BOOKS = ["draftkings", "fanduel", "betmgm"];
