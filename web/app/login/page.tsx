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
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.error || "login failed");
      }
      window.location.href = "/"; // full load so middleware sees the new cookie
    } catch (e) {
      setErr(e instanceof Error ? e.message : "login failed");
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
          Enter the password to continue.
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
          <p role="alert" className="mt-2 text-sm text-[#e0a44a]">
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
