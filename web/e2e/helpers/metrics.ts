import type { Page } from "@playwright/test";

// The numbers scripts/shots.mjs prints for every capture, read live from the
// page under test, plus the two silences a rendered page owes its reader:
// no console errors and no failed requests.

export type LayoutMetrics = {
  /** documentElement.scrollWidth - clientWidth: 0 means no horizontal scroll. */
  overflow: number;
  /** The sticky header's rendered height (globals.css --header-h is 4.25rem = 68px; the border makes 69). */
  headerHeight: number | null;
  /** Visible interactive elements narrower or shorter than 24px, with what they are. */
  targetsUnder24: string[];
  h1Count: number;
};

export async function layoutMetrics(page: Page): Promise<LayoutMetrics> {
  return page.evaluate(() => {
    const doc = document.documentElement;
    const header = document.querySelector("header");
    const targets = [
      ...document.querySelectorAll<HTMLElement>(
        "a,button,select,input,[role=button]",
      ),
    ]
      .map((el) => ({ el, r: el.getBoundingClientRect() }))
      .filter(({ r }) => r.width > 0 && r.height > 0);
    return {
      overflow: doc.scrollWidth - doc.clientWidth,
      headerHeight: header
        ? Math.round(header.getBoundingClientRect().height)
        : null,
      targetsUnder24: targets
        .filter(({ r }) => r.width < 24 || r.height < 24)
        .map(
          ({ el, r }) =>
            `${el.tagName.toLowerCase()}${el.className ? "." + String(el.className).split(/\s+/).slice(0, 2).join(".") : ""} "${(el.textContent ?? "").trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)}`,
        ),
      h1Count: document.querySelectorAll("h1").length,
    };
  });
}

export type Silence = {
  consoleErrors: string[];
  failedRequests: string[];
};

/**
 * Start collecting console errors and failed responses for a page. Call before
 * navigating; read the arrays after the page has settled.
 */
export function collectSilence(page: Page): Silence {
  const out: Silence = { consoleErrors: [], failedRequests: [] };
  page.on("console", (msg) => {
    if (msg.type() === "error") out.consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => out.consoleErrors.push(String(err)));
  page.on("requestfailed", (req) => {
    const why = req.failure()?.errorText ?? "failed";
    // A production `next start` prefetches each <Link>'s RSC payload (?_rsc=)
    // and cancels the ones it no longer needs; the browser reports those as
    // net::ERR_ABORTED. That is the client giving up, not the server failing,
    // and `next dev` never issues them at all.
    if (why === "net::ERR_ABORTED") return;
    out.failedRequests.push(`${req.method()} ${req.url()} — ${why}`);
  });
  page.on("response", (res) => {
    if (res.status() >= 400) {
      out.failedRequests.push(`${res.status()} ${res.url()}`);
    }
  });
  return out;
}
