import { glossaryTerms } from "@/lib/glossary";
import { bankrollEnv } from "@/lib/homeBoard";

// The terms, at the foot of the evidence page, next to the numbers they
// define. Two columns of one-liners, no cards and no fold: 16 boxes were the
// "too many boxes" Tate named, and a definition should cost one line
// (2026-09-16). The `#glossary` anchor is what /glossary redirects to.

export default function Glossary() {
  const { unitUsd } = bankrollEnv();
  const terms = glossaryTerms(unitUsd);
  return (
    <section id="glossary" className="mt-10">
      <h2 className="mb-2 text-sm font-semibold text-[var(--text)]">
        Terms
        <span className="ml-2 text-xs font-normal text-[var(--text-dim)]">
          {terms.length}
        </span>
      </h2>
      <dl className="grid grid-cols-1 gap-x-8 border-b border-[var(--border)] sm:grid-cols-2">
        {terms.map((t) => (
          <div
            key={t.term}
            className="border-t border-[var(--border)] py-2 text-sm leading-snug"
          >
            <dt className="inline font-semibold text-[var(--text)]">
              {t.term}
            </dt>
            <dd className="inline text-[var(--text-muted)]">
              <span className="text-[var(--text-dim)]">{" — "}</span>
              {t.body}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
