"use client";

import { useState } from "react";
import LogPickForm, { type PickPrefill } from "@/app/components/LogPickForm";

// "Log this bet" on a game page: opens the pre-filled pick form in place. The
// site reads publicly; only the password holder logs, and a visitor is shown
// nothing here (2026-09-28) — the way in is the footer's Unlock.
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
  /** Signed in (or the gate is off). False = render nothing. */
  authed: boolean;
}) {
  const [open, setOpen] = useState(false);

  if (!authed) return null;
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
