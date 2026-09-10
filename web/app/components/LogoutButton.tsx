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
      className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)] transition-colors hover:border-[var(--accent)]/45 hover:text-[var(--text)]"
    >
      Lock
    </button>
  );
}
