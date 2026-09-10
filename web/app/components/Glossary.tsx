import { glossaryTerms } from "@/lib/glossary";
import { bankrollEnv } from "@/lib/homeBoard";

// The terms, as a reference you open rather than a tab you visit. Nothing
// linked into the old /glossary page from where the words actually appear, so
// it was read once and never again; here it sits at the foot of the evidence
// page, next to the numbers it defines.

export default function Glossary() {
  const { unitUsd } = bankrollEnv();
  const terms = glossaryTerms(unitUsd);
  return (
    <details id="glossary" className="mt-8">
      <summary className="flex min-h-11 cursor-pointer items-center gap-2 text-sm font-semibold text-[var(--text)]">
        {`Every term the site uses (${terms.length})`}
        <span aria-hidden="true" className="text-xs text-[var(--text-dim)]">
          ▾
        </span>
      </summary>
      <p className="mt-1 text-xs leading-relaxed text-[var(--text-dim)]">
        If a number does not make sense, it is here.
      </p>
      <dl className="mt-3 flex flex-col gap-3">
        {terms.map((t) => (
          <div key={t.term} className="bv-card p-4">
            <dt className="text-sm font-semibold text-[var(--text)]">
              {t.term}
            </dt>
            <dd className="mt-1 text-sm text-[var(--text-muted)]">{t.body}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
