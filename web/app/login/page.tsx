"use client";

import { useState } from "react";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      // A rejected password is the only thing the endpoint can answer, so say
      // that — never the raw server message, and never "login failed".
      if (!res.ok) {
        setErr("Wrong password.");
        setBusy(false);
        return;
      }
      // A FULL load, deliberately. router.push() is a client navigation that
      // reuses the router cache and never re-runs middleware, so the board
      // would render from the pre-login cache — or bounce straight back here.
      // The lint rule is right in general and wrong for the two places that
      // change the auth cookie.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/";
    } catch {
      setErr("Could not reach the server. Try again.");
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <form onSubmit={submit} className="bv-card w-full max-w-xs p-6">
        <h1 className="font-[family-name:var(--font-display)] text-lg font-extrabold tracking-tight">
          <span className="text-[var(--accent)]">BEAT</span>
          <span className="text-[var(--text)]"> VEGAS</span>
        </h1>
        <p className="mb-4 text-sm text-[var(--text-muted)]">
          Enter the password.
        </p>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          className="bv-input w-full"
        />
        {/* Amber, not red — red is reserved for over outcomes. */}
        {err && (
          <p role="alert" className="mt-2 text-sm text-[var(--warn)]">
            {err}
          </p>
        )}
        <button type="submit" disabled={busy} className="bv-btn mt-4 w-full">
          {busy ? "…" : "Unlock"}
        </button>
      </form>
    </div>
  );
}
