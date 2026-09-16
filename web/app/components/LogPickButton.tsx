"use client";

import Link from "next/link";
import { useState } from "react";
import LogPickForm, { type PickPrefill } from "@/app/components/LogPickForm";

// "Log this bet" on a This Week card: opens the pre-filled pick form in place.
// The site reads publicly; only the password holder logs. A reader without
// the cookie gets the way in, and comes back to this game afterwards.
export default function LogPickButton({
  prefill,
  picked,
  kickedOff,
  unitUsd,
  authed,
}: {
  prefill: PickPrefill;
  /** A real-money first-half pick is already logged on this game. */
  picked: boolean;
  kickedOff: boolean;
  /** The flat stake, passed down from the server page. */
  unitUsd: number;
  /** Signed in (or the gate is off). False = show the way to /login. */
  authed: boolean;
}) {
  const [open, setOpen] = useState(false);

  if (kickedOff) {
    return (
      <span className="text-xs text-[var(--text-dim)]">
        Already kicked off.
      </span>
    );
  }
  if (picked) {
    return (
      <span className="text-xs text-[var(--text-dim)]">
        Already logged. It is on Results.
      </span>
    );
  }
  if (!authed) {
    return (
      <Link
        href={`/login?next=${encodeURIComponent(`/game/${prefill.gameId}`)}`}
        className="bv-btn bv-btn--ghost text-xs"
      >
        Unlock to log a pick
      </Link>
    );
  }
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="bv-btn text-xs"
      >
        {prefill.verdict === "BET" ? "Log this bet" : "Log as paper pick"}
      </button>
    );
  }
  return (
    <div className="mt-2 w-full">
      <LogPickForm
        prefill={prefill}
        unitUsd={unitUsd}
        onDone={() => setOpen(false)}
      />
    </div>
  );
}
