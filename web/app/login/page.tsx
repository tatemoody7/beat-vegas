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
      <form
        onSubmit={submit}
        className="w-full max-w-xs rounded-xl border border-gray-800 bg-gray-950 p-6"
      >
        <h1 className="text-lg font-semibold">Beat Vegas</h1>
        <p className="mb-4 text-sm text-gray-500">Enter the password to continue.</p>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          className="w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-gray-100 focus:border-gray-500 focus:outline-none"
        />
        {err && <p className="mt-2 text-sm text-red-400">{err}</p>}
        <button
          type="submit"
          disabled={busy}
          className="mt-4 w-full rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {busy ? "…" : "Unlock"}
        </button>
      </form>
    </div>
  );
}
