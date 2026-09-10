"use client";

import { useEffect } from "react";

/**
 * The app had no error boundary anywhere, so any throw in a page loader — a
 * Neon cold start, a dropped connection, a table the Python lane has not
 * migrated yet — rendered Next's raw 500 page. On /results that meant one
 * unavailable table took down the bankroll, the slip and the whole ledger with
 * it, with nothing on screen to say what happened or what to do.
 *
 * This says which of the two it is (the board is fine and the database is not,
 * or something is genuinely broken) and offers the retry, because a Neon cold
 * start usually succeeds on the second try.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[page]", error);
  }, [error]);

  return (
    <div className="bv-card mx-auto mt-10 max-w-xl">
      <h1 className="text-lg font-semibold">This page did not load.</h1>
      <p className="bv-empty mt-3">
        Almost always the database being briefly unreachable — Neon sleeps
        between requests and the first call after a quiet spell can time out.
        Try again; it usually works second time.
      </p>
      <p className="bv-empty mt-2">
        Nothing was changed, and no pick was logged or altered by this.
      </p>
      <div className="mt-5 flex items-center gap-3">
        <button className="bv-btn" onClick={reset}>
          Try again
        </button>
        {/* A plain <a>, not <Link>: "Try again" above is already the soft
            retry (reset()). This one is the hard escape hatch, and a client
            navigation from inside a boundary whose render just threw can land
            straight back in the same broken state. A full document load cannot. */}
        {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
        <a className="bv-btn" href="/">
          Back to the board
        </a>
      </div>
      {error.digest ? (
        <p className="bv-empty mt-4 text-xs">
          Reference <code>{error.digest}</code> — this appears in the Vercel
          runtime logs if it keeps happening.
        </p>
      ) : null}
    </div>
  );
}
