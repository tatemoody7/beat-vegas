import type { ReactNode } from "react";

// One shape for every review section on the site, and one shape for a section
// with nothing in it yet.
//
// Before this, a section with no graded rows rendered a full `bv-card` reading
// "Nothing settled yet" — and in week 2 that was eight boxes down one page,
// which reads as a broken site rather than an early season. Tate's rule
// (2026-09-10): a section with zero rows collapses to ONE PHYSICAL LINE.
//
// The caption is suppressed when the section is empty on purpose. A paragraph
// explaining the columns of a table that is not there is the placeholder
// problem again, in prose.

/** The one-line "nothing here yet" note. Never a card. */
export function EmptyLine({
  title,
  className,
  children,
}: {
  /** Optional lead-in, bolded inline before the message. */
  title?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <p className={className ? `bv-empty ${className}` : "bv-empty"}>
      {title ? <strong>{title} — </strong> : null}
      {children}
    </p>
  );
}

export default function Section({
  title,
  caption,
  empty,
  children,
}: {
  title: string;
  /** Visible explainer, never a `title=` tooltip (spec §21-§23). */
  caption?: ReactNode;
  /** When set, the whole section renders as one line carrying this message. */
  empty?: string | null;
  children?: ReactNode;
}) {
  if (empty) {
    // mt-6, not the mt-8 a live section gets: a stack of one-liners does not
    // need the same air between them as a stack of tables.
    return (
      <EmptyLine title={title} className="mt-6">
        {empty}
      </EmptyLine>
    );
  }
  return (
    <>
      <h2 className="mb-1 mt-8 text-sm font-semibold text-[var(--text)]">
        {title}
      </h2>
      {caption ? (
        <p className="mb-2 text-xs leading-relaxed text-[var(--text-dim)]">
          {caption}
        </p>
      ) : null}
      {children}
    </>
  );
}
