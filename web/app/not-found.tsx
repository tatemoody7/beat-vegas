import Link from "next/link";

/**
 * /game/[id] calls notFound() for a non-integer or unknown id, which without
 * this rendered Next's default black-and-white 404 — off the design system and
 * with no way back to the board.
 */
export default function NotFound() {
  return (
    <div className="bv-card mx-auto mt-10 max-w-xl">
      <h1 className="text-lg font-semibold">Nothing here.</h1>
      <p className="bv-empty mt-3">
        That game is not on the board. A game drops off once it is more than a
        week old, and the link may simply have aged out.
      </p>
      <div className="mt-5 flex items-center gap-3">
        <Link className="bv-btn" href="/">
          Back to the board
        </Link>
        <Link className="bv-btn" href="/results">
          Results
        </Link>
      </div>
    </div>
  );
}
