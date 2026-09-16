"use client";

export default function LogoutButton() {
  async function logout() {
    await fetch("/api/logout", { method: "POST" });
    // Full load, deliberately — see app/login/page.tsx. A client navigation
    // would leave the signed-in board sitting in the router cache after the
    // cookie that authorised it has been cleared.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/login";
  }
  return (
    <button
      onClick={logout}
      aria-label="Lock"
      className="bv-btn bv-btn--ghost shrink-0 px-2 py-1.5 text-xs font-semibold uppercase tracking-wide sm:px-3"
    >
      {/* Text at sm+, a padlock below it: the one-row phone header has no
          room for the word beside three tabs. */}
      <span className="hidden sm:inline">Lock</span>
      <svg
        aria-hidden
        className="h-3.5 w-3.5 sm:hidden"
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      >
        <rect x="3" y="7" width="10" height="7" rx="1.5" />
        <path d="M5 7V5a3 3 0 0 1 6 0v2" />
      </svg>
    </button>
  );
}
