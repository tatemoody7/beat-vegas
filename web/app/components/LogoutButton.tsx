"use client";

// "Lock" in the footer (FooterChrome): drops the cookie and returns to /login.
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
      type="button"
      onClick={logout}
      aria-label="Lock"
      className="inline-flex min-h-6 items-center underline underline-offset-2 hover:text-[var(--text)]"
    >
      Lock
    </button>
  );
}
