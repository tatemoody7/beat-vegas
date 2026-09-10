import type { NextConfig } from "next";

/**
 * Response headers. There were none, which mattered most for framing: the board
 * could be loaded in an invisible iframe on any page, and a click the owner
 * thought was landing somewhere else would run against the signed-in app with
 * their cookie attached. SameSite=Lax does not help — inside the frame the
 * request is same-site.
 *
 * Deliberately NOT a full Content-Security-Policy. A real script-src on Next's
 * App Router needs per-request nonces threaded through the framework's inline
 * bootstrap, which is a much larger change than the risk here justifies for a
 * single-user site with no third-party scripts. `frame-ancestors` is the one
 * CSP directive that carries its weight on its own, so that is what ships.
 */
const securityHeaders = [
  // The actual fix: nothing may frame this app. X-Frame-Options for older
  // engines, frame-ancestors for current ones (it wins where both are read).
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
  // Do not leak the full URL — which carries ?season=/?week=/?game= — to any
  // outbound link.
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // The CSV export is served as text/csv; stop a browser sniffing its way to
  // something executable.
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Nothing here needs hardware. Turn it all off rather than leave it open.
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  },
];

/**
 * The eleven routes the 2026-09-10 restructure moved.
 *
 * Each was a page.tsx whose whole body was a redirect() — eleven files, and
 * eleven serverless functions in every deploy, to forward a URL. Next resolves
 * these at the edge before any function runs, and `has`-free rules forward the
 * query string automatically, so ?season=/?week= still survive the hop.
 *
 * They are 308s (permanent). The moves are settled and browsers may cache them;
 * if one is ever moved again, change the destination here rather than adding
 * another hop.
 */
const movedRoutes: { source: string; destination: string }[] = [
  // -> the board
  { source: "/board", destination: "/" },
  { source: "/preview", destination: "/" },
  { source: "/line-check", destination: "/" },
  // /movement carried a ?game=. The old stub stripped it; a config redirect
  // always forwards the query, so it arrives at the board and is ignored there.
  // Not worth a `has` rule to strip: movement lives on the game page now, and
  // an unread parameter costs nothing.
  { source: "/movement", destination: "/" },
  // -> the money page
  { source: "/ledger", destination: "/results" },
  { source: "/picks", destination: "/results" },
  { source: "/weekly-review", destination: "/results" },
  // -> the track record
  { source: "/line-study", destination: "/proof" },
  { source: "/research", destination: "/proof" },
  { source: "/research/records", destination: "/proof/records" },
  { source: "/glossary", destination: "/proof#glossary" },
];

const nextConfig: NextConfig = {
  async redirects() {
    return movedRoutes.map((r) => ({ ...r, permanent: true }));
  },
  // Next 16.3 writes its own AGENTS.md and CLAUDE.md into this directory on
  // every dev start. The project's brief is the root CLAUDE.md; a second one
  // under web/ would be auto-loaded alongside it and quietly compete with it,
  // and neither file is something we authored. Off.
  agentRules: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
