"use client";

import { useState } from "react";
import LogPickForm, { type PickPrefill } from "@/app/components/LogPickForm";

// "Log this bet" on a This Week card: opens the pre-filled pick form in place.
export default function LogPickButton({
  prefill,
  picked,
  kickedOff,
  unitUsd,
}: {
  prefill: PickPrefill;
  /** A real-money first-half pick is already logged on this game. */
  picked: boolean;
  kickedOff: boolean;
  /** The flat stake, passed down from the server page. */
  unitUsd: number;
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
