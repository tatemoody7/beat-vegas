"use client";

export default function LogoutButton() {
  async function logout() {
    await fetch("/api/logout", { method: "POST" });
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
