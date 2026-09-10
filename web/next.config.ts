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

const nextConfig: NextConfig = {
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
