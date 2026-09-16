# Redesign workflow and tooling research — Beat Vegas web app

Written 2026-09-16 for the redesign discovery session. Target: Next.js 16 App Router,
Tailwind v4, Recharts 3.10, Vercel, ~30 components, 3 pages + `/game/[id]`, dark theme,
one expert user, owner + Claude Code iterating page by page with screenshot comparison.

Note: plan mode was active in the research session, so this file was written here
instead of `scratchpad/research_workflow.md`. Copy or move it if the scratchpad path
is what the plan expects.

What I checked in the repo before writing (read-only): `web/package.json` (Recharts
^3.10.1, no Playwright), `web/app/layout.tsx` (Geist + Geist Mono + Archivo via
`next/font/google`), `web/app/globals.css` (517 lines, `tabular-nums` already on numeric
cells), the three Recharts call sites (`BankrollCurve`, `GapLadderChart`,
`LineStudyView`), and the scratchpad `pw/shots.js` (Playwright 1.57, `channel: "chrome"`,
1440 desktop context + `devices['iPhone 13']`, `fullPage` + fold captures, a
`report.json` of heights/overflow/headings).

---

## 1. Design system first vs page by page

**Recommendation: a short foundations pass first (half a day, not a project), then page
by page — and sequence the pages by decision weight: Board, then `/game/[id]`, then
Results, then Track record.**

The foundations pass is only what the inventory already says is missing or broken:

- Type scale as Tailwind v4 `@theme` `--text-*` tokens (the inventory found `text-xs`
  and `text-sm` carrying 88% of type plus ~9 one-off rem sizes).
- A spacing rhythm (there are no spacing tokens today).
- Surface ladder for elevation (see section 6) replacing the 4 non-token greys in
  `BankrollCurve` and the one-off amber on login.
- Delete the dead classes (`.bv-stat`, `.bv-badge--solid*`, `.bv-fac-tier`,
  `.bv-badge--wrap`), collapse `--border-soft` -> `--border`, give `--push` its own value
  or drop it, and make the one filter-chip style shared.

Then stop. Do not build a component library or a Storybook. Everything else is decided
on a real page with real data.

Why this split, with sources:

- Brad Frost's interface inventory is exactly the step already done in the discovery
  session ("a comprehensive collection of the bits and pieces that make up your
  interface"; it lets you "display an interface as a system of components rather than a
  series of discrete pages"). Its purpose is to expose redundancy and scope the work,
  not to mandate a system-first build.
  https://bradfrost.com/blog/post/interface-inventory/
- Frost's own workflow chapter is explicit that static comps are for "facilitat[ing] a
  conversation" and that "Once the designs are in the browser, they should stay in the
  browser." It also carries Dan Mall's line: "Let's change the phrase 'designing in the
  browser' to 'deciding in the browser.'"
  https://atomicdesign.bradfrost.com/chapter-4/
- Refactoring UI's opening rules: "Start with a feature, not a layout", "Detail comes
  later", "Don't design too much", "Limit your choices", and later "Establish a type
  scale" and "Define your shades up front". That is the whole argument for a small
  tokens pass followed by feature-by-feature work: pick the palette of options once so
  every later decision is a choice among 5 sizes rather than a fresh invention.
  https://refactoringui.com/
- Linear's 2024 redesign (the closest published precedent: small team, existing
  product, dark theme, six weeks) explicitly rejected the atomic route: "A redesign
  should not completely disassemble the product to its atomic parts." They sequenced by
  surface (stress tests across 8 core views, then behaviour definitions, then sidebar
  and chrome under a feature flag, then beta), compared old vs new with an internal
  toolbar toggling the flag, and kept the navigation overhaul out of scope. Also:
  "It's always better to do a redesign quickly. Otherwise, you will block almost every
  project."
  https://linear.app/now/how-we-redesigned-the-linear-ui and
  https://linear.app/now/a-design-reset
- Tailwind v4 makes the tokens pass cheap: `@theme` variables are both CSS variables and
  the source of utilities ("Theme variables aren't just CSS variables — they also
  instruct Tailwind to create new utility classes"), and a namespace can be replaced
  wholesale with `--color-*: initial`. So the type scale and surface ladder land in one
  block of `globals.css`, and `text-xs`/`text-sm` can be re-pointed rather than
  find-and-replaced. https://tailwindcss.com/docs/theme
- For a single-platform, one-user app, the token literature itself says CSS variables
  are enough; full token pipelines earn their keep with multiple platforms or teams
  (UXPin's guide: "for small, single-platform projects, CSS variables or a simple style
  guide may suffice"). https://www.uxpin.com/studio/blog/what-are-design-tokens/

Trade-offs:

- Tokens first: cheap here (they already exist in `globals.css`), prevents the Linear
  "design debt from incremental changes" problem re-accumulating during the page pass,
  and lets a later page change ride on the first page's decisions. Risk is scope creep
  into a system nobody uses; cap it at the list above.
- Page by page only: fastest visible progress; risk is four pages that each invent a
  spacing rhythm, which is how the current state happened.
- System first (Storybook, full component pass): wrong size for 30 components and one
  user; adds a second rendering environment to keep in sync (the Storybook/Figma
  duplication problem UXPin describes).

## 2. Claude Design

**What it is (verified against Anthropic's announcement and the help centre).**
Claude Design, released by Anthropic Labs on 2026-04-17, is a chat-plus-canvas tool
for "designs, interactive prototypes, presentations, and more". It can read a codebase
or design files to build a design system ("Claude builds a design system for your team
by reading your codebase and design files. Every project after that uses your colors,
typography, and components automatically"). Exports: internal URL, download as .zip,
PDF, PPTX, "Export as standalone HTML", send-to integrations (Adobe, Base44, Canva,
Gamma, Lovable, Miro, Replit, Vercel, Wix), and "Handoff to Claude Code" (local or
web). Direct canvas editing: "drag, resize, and align elements directly". Beta on Pro,
Max, Team, Enterprise; web and desktop only; usage draws from the shared plan pool.
https://www.anthropic.com/news/claude-design-anthropic-labs
https://support.claude.com/en/articles/14604416-get-started-with-claude-design

**Export format is HTML, not React.** The official pages say "standalone HTML files";
the Vercel MCP tool available in this very session, `import-claude-design-from-url`,
describes its input as "a self-contained HTML bundle with all images, fonts, and styles
inlined" fetched from a public URL valid ~1 hour, with a `claude_design_project_id` to
re-import into the same Vercel project. The Vercel KB likewise describes the export as
"a zipped folder of website files" with an `index.html`. Claims of React/SVG component
export in third-party write-ups are not in the official docs.
https://vercel.com/kb/guide/claude-design
https://vercel.com/changelog/claude-design-and-vercel (2026-06-23)

**Claude Code integration, three pieces:**

- `/design` skill (research preview, Claude Code v2.1.234+, week of 2026-08-17): "brings
  Claude Design's artboard workflow into the CLI and Claude Code Desktop, built on
  artifacts. Run it with a brief and Claude publishes a canvas of editable artboards
  for your UI. Pick one, tweak it, then have Claude implement it." The artboards are
  `.dc.html` files on one pan/zoom canvas; where saving is enabled you get
  click-to-select, a properties panel, inline text editing, undo/redo and a Save that
  republishes; otherwise view-and-export PNG/PDF.
  https://code.claude.com/docs/en/whats-new/2026-w34
- `DesignSync` tool / `/design-sync`: keeps a local component library in sync with a
  claude.ai/design design-system project "incrementally, one component at a time". The
  tool description (as published in the Piebald system-prompt mirror) is push-oriented:
  list/read, finalise a plan, then write/delete, 256 KiB per file, 256 files per call,
  `@dsCard` markers for previews. Third-party write-ups add that the renderer runs
  React, so components must mount inside it (a built `dist/` or Storybook); Vue,
  Svelte and Angular are out.
  https://github.com/Piebald-AI/claude-code-system-prompts/blob/main/system-prompts/tool-description-designsync.md
  https://wmedia.es/en/tips/claude-code-design-sync-your-components
- Handoff bundle: design files, the chat history that produced them, and a README with
  a prompt; "most valuable when your codebase is linked". The documented failure mode
  is cross-session drift: designs made on different days "re-derived" the system each
  time, so heading scales and accent placement diverged — the fix is a written rules
  file the agent consults. https://flowpoint.ai/blog/claude-design-to-claude-code

**When it is worth it here — recommendation: use `/design` narrowly, for two or three
divergent Board-row concepts, and nothing else.**

- Worth it for: the one place where the *shape* of the answer is open — what a board
  row is (card vs dense row vs grouped list), what the answer bar is. Three side-by-side
  artboards with real week-3 text pasted in beats three sequential code iterations,
  because the comparison is simultaneous and the cost of a rejected option is near zero.
  Element collages (Dan Mall) are the same idea: explore the header without the
  stakeholder's eye wandering to the rest of the page.
- Not worth it for: everything after the direction is chosen. The site is already in
  code with live data, dark theme, real edge cases (39 of 57 rows saying "Not yet"),
  server gates that must not move, and a `pw/shots.js` pipeline. A `.dc.html` artboard
  is a static picture of one state; the redesign's hard problems are states (0 bets,
  paper-only, LIVE/FINAL, folds) and density, which only show in the browser. Round-
  tripping through `/design-sync` also means a React `dist/` build of the component
  library that does not exist and would have to be maintained.
- Concretely: `/design` produces HTML artboards, not Tailwind components; Claude Code
  still has to re-implement against `globals.css` tokens. Treat it as a sketching
  surface, the same role Shape Up gives fat-marker sketches.

Trade-offs: `/design` gives Tate direct manipulation (he can drag a gap wider himself)
and instant A/B/C; it costs a hop that can drift from the real tokens and cannot show
data-driven states. Iterating in code gives truth (real data, real fonts, real widths)
and a diffable history; it costs one iteration per idea.

## 3. Wireframes vs hi-fi mockups vs design in the browser

**Recommendation: one round of low-fi structure decisions on paper or in a
`/design` artboard for the Board and the game page (what goes, what stays, order of
blocks), then everything else in the browser. No hi-fi mockups at all.**

Arguments for low-fi first (structure and IA):

- Shape Up: "If we start with wireframes or specific visual layouts, we'll get stuck on
  unnecessary details and we won't be able to explore as broadly as we need to." Fat
  marker sketches exist "to avoid easily skipping ahead to the wrong level of fidelity".
  And on hi-fi: "any specific mockups are going to bias what other people do after
  you… They'll take every detail in the initial mockups as direction even though you
  didn't intend it." https://basecamp.com/shapeup/1.3-chapter-04
- Refactoring UI: work in grayscale first so "you're forced to use spacing, contrast,
  and size to do all of the heavy lifting" — the Board's problem is exactly hierarchy
  (45 green badges, zero bets), which a low-fi pass exposes and colour hides.
  https://refactoringui.com/
- The inventory critique is mostly IA, not skin: the gap stated four times on the game
  page, the answer bar duplicating rows 1–3, the book table as the tallest block. Those
  are "does this block exist and where" decisions — the cheapest place to make them is
  a list or a box sketch, before any pixel work.

Arguments for designing in code (this app):

- Frost: working in the browser lets you "address layout issues across the entire
  resolution spectrum, design around dynamic data … demonstrate interaction and
  animation, gauge performance". The Board at 390 grows 520px from logos alone (project
  memory) — a mockup would never have shown it.
  https://atomicdesign.bradfrost.com/chapter-4/
- Patrick Morgan (UX Collective) and UXPin make the practical case: every decision
  lives "in the same environment it will ship in — the browser — with no assumptions
  about interactions, no lost states". A hi-fi Figma/Claude Design mock of a
  one-user tool is a second artifact to keep in sync with no one to hand it to.
  https://uxdesign.cc/why-i-skipped-figma-and-prototyped-in-code-instead-8d1dab51c07d
  https://www.uxpin.com/studio/blog/why-development-technical-design-teams-choose-code-based-design-over-figma/
- NN/g on iteration: median 38% usability gain per iteration, 165% first-to-last, and
  "Three versions (two iterations) should probably be the minimum." Iterating in code
  with screenshots is how you get to three versions of the Board in an afternoon.
  https://www.nngroup.com/articles/iterative-design/

Trade-off summary: low-fi costs almost nothing and prevents polishing a block that
should not exist; hi-fi costs a day per page and locks in details early; in-browser is
the only place density, states and mobile are true, but each idea costs an iteration —
so use low-fi to cut the number of ideas that reach the browser.

## 4. Visual regression / before-after tooling

**Recommendation: keep `pw/shots.js`, move it into the repo as `web/scripts/shots.mjs`
(Playwright dev-dependency, `channel: "chrome"`), and add two small pieces: `odiff` for
pixel diffs and an ImageMagick `montage` step for side-by-side composites. Skip
Storybook, Chromatic, Percy, Argos and Lost Pixel.**

Why not the hosted or component tools:

- Lost Pixel: site banner reads "Lost Pixel is joining Figma. We are sunsetting the
  product and building what's next." Do not adopt. https://www.lost-pixel.com/
- Chromatic: free 5,000 snapshots/month, Starter $179/month; it is Storybook-centred and
  the app has no Storybook. https://www.chromatic.com/pricing
- Argos: free 5,000 screenshots/month, Pro $100/month; open-source-friendly and works
  from Playwright captures, but it is a CI review UI for a team. One user comparing two
  PNGs does not need a PR gate. https://argos-ci.com/pricing
- Percy: $599/month entry per Argos's comparison; irrelevant at this scale.
  https://argos-ci.com/blog/percy-vs-chromatic-vs-argos
- Playwright `toHaveScreenshot`: the right tool for *regression* (locking a finished
  page), the wrong tool for *iteration* (it fails on every intended change and you
  `--update-snapshots` constantly). Adopt it at the end of the redesign, per page, once
  a page is signed off. Defaults worth knowing: `animations: "disabled"`, `caret:
  "hide"`, `scale: "css"`, `threshold: 0.2` (YIQ), `maxDiffPixels`/`maxDiffPixelRatio`
  unset unless configured, `stylePath` to neutralise volatile elements, `mask` for
  live-data regions. Baselines are named per browser+platform (`chromium-darwin`) and
  Playwright warns rendering varies with OS, headless mode and even power source, so
  keep them local to this Mac. https://playwright.dev/docs/test-snapshots
  https://playwright.dev/docs/api/class-pageassertions

The local setup (simplest that works):

1. **Capture** — the existing script already does the important things: `waitUntil:
   'networkidle'` + settle, `fullPage: true` plus a fold shot, per-page
   `scrollHeight`/overflow/headings to `report.json`. Changes to make:
   - Desktop context stays `1440x900, dpr 1`. Mobile: `devices['iPhone 14']` is
     390x664 @3x (verified in Playwright's device registry; iPhone 13 is the same
     390 width). Set `deviceScaleFactor: 1` on a *second* mobile context if diffs are
     to be cheap — a 3x capture of an 11,000px board is a 1170x33,000 image. Keep one
     3x capture per page for eyeballing text rendering.
   - Add `colorScheme: 'dark'` explicitly so the capture does not depend on the Mac's
     appearance (Playwright emulation docs). https://playwright.dev/docs/emulation
   - Add `reducedMotion: 'reduce'` and rely on `animations: 'disabled'` semantics —
     Recharts 3 defaults `isAnimationActive` to `"auto"`, which honours
     `prefers-reduced-motion`, and the repo already found that bars need
     `isAnimationActive={false}` to render at all. https://recharts.github.io/en-US/api/Bar/
   - Name files `<page>_<viewport>_<gitsha-or-label>.png` so before/after pairs are
     addressable: `board_1440_before.png` / `board_1440_after.png`.
   - Keep the sticky header in mind: full-page stitching can repeat a fixed header;
     Playwright's `stylePath` can set it `position: static` for the capture.
2. **Diff** — `npm i -D odiff-bin`; `odiff before.png after.png diff.png --antialiasing
   --threshold 0.1`. Same YIQ algorithm as pixelmatch but SIMD, "6 times faster";
   `--fail-on-layout-diff` exits when heights differ, which is itself the signal you
   want (the page got shorter). Exit code 0 = identical, 1 = layout differs, 22 = pixels
   differ. https://github.com/dmtrKovalenko/odiff
   Heights differ on almost every redesign step, so most diffs will be layout diffs;
   the pixel diff is useful for "did this CSS change touch anything else".
3. **Composite** — ImageMagick, already the standard for this:
   `magick montage before.png after.png -tile 2x1 -geometry +24+0 -background '#0b0f16'
   -label '%t' side_by_side.png` (pad the shorter image to the taller one first with
   `-gravity north -extent`). For mobile, tile before/after/diff `3x1`. Crop the top
   1,600px for the chat (`-crop 2900x1600+0+0`) and let the full composite live on disk;
   the memory note about not reading 12,000px images into context stands.
   https://www.micski.dk/2026/01/23/how-to-compare-images-side-by-side-as-a-montage-with-imagemagick/
4. **Numbers beside pictures** — extend `report.json` per capture with: page height at
   both widths, count of `h1–h3`, count of interactive elements under 24x24 CSS px
   (section 5), any element whose `getBoundingClientRect().right > clientWidth`, and
   the largest text node under 12px. Print the before/after delta as a table. This is
   the "look at the picture, not just scrollHeight" lesson from PR #122 applied both
   ways: the picture catches what the DOM cannot, the numbers catch what the eye skims.

Chrome DevTools device mode is the interactive equivalent of Playwright's device
descriptor (viewport, DPR, UA, touch, CPU/network throttle) and explicitly "you don't
actually run your code on a mobile device". Use it for poking, not for captures; the
Browser pane's screenshots are known-useless here but its `javascript_tool` works for
the overflow check. https://developer.chrome.com/docs/devtools/device-mode

Trade-offs: this stack is three CLIs and zero services; the cost is that nothing
stops a regression until `toHaveScreenshot` is added at sign-off. Argos would give a
hosted review UI and baseline management from git for free at this volume, but it is
a PR workflow for a team and adds a network dependency to a one-person loop.

## 5. Usability over aesthetics — a checklist for one expert user

**Recommendation: three task timings, one 5-second test per page, the heuristics that
matter for a decision tool, and five measured numbers per capture. Run the whole thing
on the current site first so "after" has a "before".**

Sources: NN/g's ten heuristics (https://www.nngroup.com/articles/ten-usability-heuristics/),
success rate as "the bottom line of usability" with the warning not to average ordinal
levels (https://www.nngroup.com/articles/success-rate-the-simplest-usability-metric/),
the 5-second test as a first-impression probe (https://www.nngroup.com/videos/5-second-usability-test/,
method detail at https://www.lyssna.com/guides/five-second-testing-guide/), WCAG 2.5.8
target size 24x24 CSS px at AA with 44x44 the AAA/Apple/Material ergonomic target
(https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html), WCAG 1.4.3
4.5:1 / 3:1 (https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).

**A. Tasks (time them with a phone stopwatch, Tate does them cold, once before and
once after each page ships; record success/partial/fail and seconds — do not average
the levels):**
1. "What do I bet this week?" — from opening `/` to naming the games and the price
   needed. Target: under 10 seconds, no scroll on desktop, one screen on mobile.
2. "Why is game X not a bet?" — from `/` to the blocker in words on `/game/[id]`.
3. "How am I doing for real money this season?" — `/results`, two numbers, no clicks.
4. "Did the rule beat me last week?" — `/results` paper vs real, one screen.
5. "Log this paper pick" — from the board row to a logged pick, count taps.

**B. 5-second test, one per page:** show the fold capture for five seconds, hide it,
ask "what is this page telling you to do?" and "which number did you see first?". If the
answer is not "these N games / no bets this week" on the Board, the hierarchy failed
regardless of how it looks. Lyssna's guidance: ask the most important question first,
do not brief the participant on what will be asked.

**C. Heuristics that bite a one-user decision tool (skip the rest):**
- #1 Visibility of system status — stale-results banner, missed build, next build
  window, LIVE/FINAL: visible without scrolling?
- #6 Recognition over recall — kill price shown next to the current price, never
  "needs -1xx" without the current -1xx beside it.
- #8 Aesthetic and minimalist — "Interfaces should not contain information that is
  irrelevant or rarely needed": the gap stated four times, 39 rows repeating the same
  sentence, a 10-row book table of "no move".
- #4 Consistency — one filter-chip style, one button style, green means one thing.
- #5 Error prevention — the server gates already do this; the UI's job is to make the
  rejection read as the rule, not an outage (the `PRICE UNAVAILABLE` distinction).

**D. Five numbers per capture (scripted in `shots.mjs`, before/after):**
1. Page height at 1440 and 390 (Board today 7,396 / 11,053).
2. Scroll depth to the first actionable answer (offsetTop of the first BET row or the
   "no bets" line).
3. Interactive targets under 24x24 CSS px (WCAG AA floor) and under 44x44 (target),
   listed by selector.
4. Text nodes under 12px, and any body text under 4.5:1 or large text under 3:1 against
   its computed background (compute with the WCAG formula in-page; note that WCAG 2's
   ratio is known to overstate contrast on dark backgrounds, so treat 4.5:1 as a floor
   and prefer the 7:1 Apple suggests for small custom colours —
   https://git.apcacontrast.com/documentation/WhyAPCA.html).
5. Reading order: dump `h1–h3` and the first 12 focusable elements in DOM order; it
   should read like the answer, and the tab order should reach "log pick" before the
   book table.
6. Horizontal overflow at 390 (`scrollWidth - clientWidth`), must stay 0.

Trade-offs: with n=1 nothing here is statistics; it is a ratchet. The point is that
"looks better" is not allowed to ship a page whose task-1 time or first-answer scroll
depth got worse.

## 6. Dark-theme data UI craft

Sources: Material dark theme (https://m2.material.io/design/color/dark-theme.html —
values below are the published ones, confirmed via the Material codelab and
secondary write-ups), Apple HIG Dark Mode
(https://developer.apple.com/design/human-interface-guidelines/dark-mode), Refactoring
UI chapter titles (https://refactoringui.com/), halation guidance
(https://www.colorcontrast.org/blog/dark-mode-contrast-accessibility-guide/).

- **Elevation by lightness, not shadow.** Material: "the higher a surface's elevation
  … the lighter that surface becomes", implemented as a white overlay from 0% at 0dp to
  16% at 24dp over a `#121212` base. Apple: two sets, "base" and "elevated", where "the
  base colors are darker, making background interfaces appear to recede, and the
  elevated colors are lighter". For this app: a 3-step ladder (canvas, card, raised
  card/popover) as tokens, and delete the two shadow tokens or keep one for popovers
  only. Refactoring UI's "Emulate a light source" is written for light UIs; on dark
  canvases the light source is expressed as the surface getting lighter, not as a
  drop shadow, and "Use fewer borders" applies doubly — a lighter surface can replace
  most borders.
- **Not pure black, not pure white.** Material recommends `#121212` "rather than
  black" because grey "can express a wider range of color, elevation, and depth".
  Pure white on pure black maximises halation ("a glowing or halo effect around text")
  and is hardest on astigmatic readers; use off-white (`#E0E0E0`–`#F0F0F0` range) for
  body text and reserve near-white for the hero numbers. Material's own text
  opacities: high-emphasis 87%, medium 60%, disabled 38% white.
- **Desaturated accents.** Material's dark baseline uses the 200 tone of the primary
  ("a less saturated and more luminous tone, typically 200") so it passes 4.5:1 "at all
  elevation surfaces"; saturated colours "visually vibrate" on dark. The electric cyan
  is chrome only here (links, active nav) — keep it, but check it against the lightest
  surface in the ladder, and desaturate the good/warn/bad trio so the green does not
  glow across 45 rows.
- **Contrast targets.** WCAG AA 4.5:1 body / 3:1 large is the floor and is the same on
  dark; Material notes white text needs 15.8:1 against the base so it still clears
  4.5:1 on the lightest elevated surface; Apple suggests "a contrast ratio of 7:1,
  especially for smaller text" for custom colours. WCAG 2's formula overstates
  contrast for dark pairs, so treat 4.5:1 as necessary, not sufficient.
- **Refactoring UI colour rules that carry over:** "Don't use grey text on colored
  backgrounds" (use a tinted, lower-opacity version of the foreground instead), "Greys
  don't have to be grey" (tint the surface ladder toward the navy hue rather than
  neutral grey), "Don't rely on color alone" (the rank number and the word must carry
  the grade, which the board already does).
- **Numbers.** Tabular figures on every column and every live number (already on
  numeric cells in `globals.css` — extend to the answer bar and stat tiles); right-align
  numeric columns; minimum 12px for any number that has to be read, 11px only for axis
  ticks. Stéphanie Walter: "10px and even 12px is usually really small in many cases"
  and reducing size is "an 'easy' way to display a LOT of data" — prefer progressive
  disclosure (the existing `Fold`) over shrinking.
  https://stephaniewalter.design/blog/what-minimum-font-size-for-a-high-density-data-web-app-do-you-suggest/
- **Large colour areas.** The eight full-width tinted factor bars on the game page are
  the kind of large saturated area dark-theme guidance warns against; a thin bar or a
  number with a small swatch does the same job.

## 7. Typography for a numbers-heavy dark UI

**Recommendation: keep Geist Sans as the UI face, drop Archivo unless it is doing
something Geist at 700–800 cannot, and stop using Geist Mono for numbers — use Geist
Sans with `font-variant-numeric: tabular-nums` (plus `slashed-zero` where 0/O
ambiguity exists) for every figure. Keep mono for genuinely code-like strings (ids,
prices in a log). One caveat to verify before deciding: Vercel's own comparison table
says the Google Fonts build of Geist lacks `font-feature-settings` support; the npm
`geist` package has the full OpenType table. The app loads Geist through
`next/font/google`, so test whether `tabular-nums` actually takes effect in the
current build; if not, switch to the npm package (same font, one import change).**
https://vercel.com/font (feature-support table; the page names "Tabular numbers" among
Geist's features per https://lexingtonthemes.com/blog/geist-opentype-features)

Should numbers be monospace? No, not by default.

- Tabular lining figures give the alignment benefit ("every digit the same horizontal
  space so columns align") without the monospace costs: a code font makes "your
  dashboard look like a terminal", ships wider glyphs, and forces letters into equal
  widths too. The rule from the DEV write-up: "if you're using a monospace font purely
  to stop digits from jittering, you almost certainly want `font-variant-numeric:
  tabular-nums` instead". MDN: `tabular-nums` maps to OpenType `tnum`, Baseline widely
  available. Apple ships the same idea as `monospacedDigitSystemFont` — the system font
  with fixed-width digits, not SF Mono.
  https://dev.to/alanwest/tabular-numbers-in-css-font-variant-numeric-vs-monospace-hacks-25cn
  https://developer.mozilla.org/en-US/docs/Web/CSS/font-variant-numeric
  https://developer.apple.com/documentation/uikit/uifont/monospaceddigitsystemfont(ofsize:weight:)
- Where mono still earns its place: a single column of prices that must scan as a
  ledger, or where the typographic *voice* of "engineering readout" is wanted. Vercel
  uses tabular Geist Sans in tables and metrics for exactly that reason; it does not
  set them in Geist Mono.

Font options, if Geist is reconsidered:

- **Inter** (free): full `tnum`, `zero`, `case`, `ss01–ss08`, and text/display optical
  sizes — the safest numbers-first sans; more neutral than Geist, slightly wider.
  https://rsms.me/inter/
- **IBM Plex Sans + Plex Mono** (free): true superfamily so the mono and sans share
  metrics; Plex Sans has `tnum`; warmer, more character than Geist; a good fit if the
  brand wants "ledger" rather than "Swiss".
- **JetBrains Mono / Berkeley Mono**: coding fonts; Berkeley is paid and "noticeably
  more refined", JetBrains is free with a tall x-height. Both are only relevant if
  the decision is to keep a mono for numbers — and by construction every mono has
  tabular figures, so the choice is aesthetic.
- **Söhne / SF**: Söhne is licensed (Klim) and SF is not licensed for the web outside
  Apple platforms; neither is a practical option here.

Pairing: one family plus tabular figures is the least-decision path (Refactoring UI:
"Limit your choices"). Two families (Geist + a display face) is defensible only if the
display face carries the two or three hero numbers; three (Geist, Geist Mono, Archivo)
is the current state and is where the 9 one-off sizes came from.

## 8. Recharts vs alternatives

**Recommendation: keep Recharts for the redesign; do not switch libraries mid-redesign.
Revisit only if bundle size or the animation footgun causes a measured problem. If the
final design keeps exactly two charts (bankroll curve, gap ladder), hand-rolled SVG is
the better end state and is a separate, small follow-up.**

Facts:

- Recharts 3.10.1 on Bundlephobia: 566 KB minified, 151 KB gzipped, 11 dependencies
  (it now carries Redux Toolkit, Immer and react-redux). A treeshaken import of a few
  components lands around 70 KB gzipped per a like-for-like comparison; visx core is
  ~25 KB gzipped but "developers must manually construct axes, grids, and legends".
  That comparison's verdict for a 3-chart dashboard: "Recharts wins on DX".
  https://bundlephobia.com/package/recharts
  https://gist.github.com/kevinnft/8e2313a2c43d05be37c374ae6249a475
- Recharts 3's `isAnimationActive="auto"` respects `prefers-reduced-motion` and is
  disabled in SSR; the repo already learned bars need `isAnimationActive={false}` to
  render. https://recharts.github.io/en-US/api/Bar/
- Observable Plot renders to a DOM node and is used in React through `useRef` +
  `useEffect` + `Plot.plot()` + `append` — a client-only imperative island, which fits
  poorly with an App Router page that is otherwise server-rendered.
  https://observablehq.com/plot/getting-started
- Chart.js is canvas: good for many points and frequent updates, worse for crisp text
  and CSS-token colours on a dark theme; wrong shape for two static charts.
- Plain SVG: a bankroll line is one `<path>` and a few `<text>` ticks; the gap ladder is
  five `<rect>`s. Both render server-side with no client JS, take CSS variables
  directly, never animate, and are diffable in a screenshot. Cost: axis tick maths and
  the tooltip, if a tooltip is wanted at all ("if it isn't obvious I don't want it"
  argues it is not).

Trade-offs: switching now couples a library migration to a visual redesign and
doubles the surface of every screenshot diff; keeping Recharts costs ~70–150 KB of
client JS on two pages one person opens. The three call sites (`BankrollCurve`,
`GapLadderChart`, `LineStudyView`) are small enough that a later swap to SVG is a
one-afternoon change if the design settles on charts that never need interaction.

---

## Sources (all consulted 2026-09-16)

- https://www.anthropic.com/news/claude-design-anthropic-labs
- https://support.claude.com/en/articles/14604416-get-started-with-claude-design
- https://code.claude.com/docs/en/whats-new/2026-w34
- https://vercel.com/changelog/claude-design-and-vercel
- https://vercel.com/kb/guide/claude-design
- https://github.com/Piebald-AI/claude-code-system-prompts/blob/main/system-prompts/tool-description-designsync.md
- https://wmedia.es/en/tips/claude-code-design-sync-your-components
- https://blakecrosley.com/blog/claude-code-design-skill
- https://flowpoint.ai/blog/claude-design-to-claude-code
- https://bradfrost.com/blog/post/interface-inventory/
- https://atomicdesign.bradfrost.com/chapter-4/
- https://refactoringui.com/
- https://linear.app/now/a-design-reset
- https://linear.app/now/how-we-redesigned-the-linear-ui
- https://tailwindcss.com/docs/theme
- https://www.uxpin.com/studio/blog/what-are-design-tokens/
- https://basecamp.com/shapeup/1.3-chapter-04
- https://uxdesign.cc/why-i-skipped-figma-and-prototyped-in-code-instead-8d1dab51c07d
- https://www.uxpin.com/studio/blog/why-development-technical-design-teams-choose-code-based-design-over-figma/
- https://www.nngroup.com/articles/iterative-design/
- https://www.nngroup.com/articles/ten-usability-heuristics/
- https://www.nngroup.com/articles/success-rate-the-simplest-usability-metric/
- https://www.nngroup.com/videos/5-second-usability-test/
- https://www.lyssna.com/guides/five-second-testing-guide/
- https://playwright.dev/docs/test-snapshots
- https://playwright.dev/docs/api/class-pageassertions
- https://playwright.dev/docs/emulation
- https://cdn.jsdelivr.net/npm/playwright-core/lib/server/deviceDescriptorsSource.json
- https://github.com/dmtrKovalenko/odiff
- https://www.micski.dk/2026/01/23/how-to-compare-images-side-by-side-as-a-montage-with-imagemagick/
- https://www.lost-pixel.com/
- https://www.chromatic.com/pricing
- https://argos-ci.com/pricing
- https://argos-ci.com/blog/percy-vs-chromatic-vs-argos
- https://developer.chrome.com/docs/devtools/device-mode
- https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- https://git.apcacontrast.com/documentation/WhyAPCA.html
- https://m2.material.io/design/color/dark-theme.html
- https://codelabs.developers.google.com/codelabs/design-material-darktheme
- https://developer.apple.com/design/human-interface-guidelines/dark-mode
- https://www.colorcontrast.org/blog/dark-mode-contrast-accessibility-guide/
- https://stephaniewalter.design/blog/what-minimum-font-size-for-a-high-density-data-web-app-do-you-suggest/
- https://developer.mozilla.org/en-US/docs/Web/CSS/font-variant-numeric
- https://dev.to/alanwest/tabular-numbers-in-css-font-variant-numeric-vs-monospace-hacks-25cn
- https://developer.apple.com/documentation/uikit/uifont/monospaceddigitsystemfont(ofsize:weight:)
- https://vercel.com/font
- https://lexingtonthemes.com/blog/geist-opentype-features
- https://rsms.me/inter/
- https://bundlephobia.com/package/recharts
- https://gist.github.com/kevinnft/8e2313a2c43d05be37c374ae6249a475
- https://recharts.github.io/en-US/api/Bar/
- https://observablehq.com/plot/getting-started
