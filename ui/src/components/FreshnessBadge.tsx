import type { Quote } from "@/api/types";
import { formatInr, formatStaleness } from "@/lib/format";

const LABELS = {
  fresh: { text: "Live", dot: "bg-fresh", tone: "text-fresh" },
  delayed: { text: "Delayed", dot: "bg-delayed", tone: "text-delayed" },
  stale: { text: "Stale", dot: "bg-stale", tone: "text-stale" },
  disputed: { text: "Disputed", dot: "bg-disputed", tone: "text-disputed" },
  closed: { text: "Closed", dot: "bg-closed", tone: "text-closed" },
} as const;

export function FreshnessBadge({ quote }: { quote: Quote }) {
  const label = LABELS[quote.confidence];

  return (
    <span
      className="inline-flex items-center gap-1.5 text-[11px] font-medium tracking-wide uppercase"
      title={`${quote.source.toUpperCase()} · ${formatStaleness(quote.staleness_seconds)}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${label.dot}`} aria-hidden />
      <span className={label.tone}>{label.text}</span>
      <span className="text-faint normal-case tracking-normal">
        {formatStaleness(quote.staleness_seconds)}
      </span>
    </span>
  );
}

export function DisputedPrices({ quote }: { quote: Quote }) {
  if (!quote.alt || quote.divergence_pct === null) return null;

  return (
    <p className="mt-3 rounded-md border border-disputed/30 bg-disputed/5 px-3 py-2 text-xs text-muted">
      Two sources disagree by{" "}
      <span className="numeric text-disputed">
        {quote.divergence_pct.toFixed(2)}%
      </span>
      : {quote.source.toUpperCase()} quotes{" "}
      <span className="numeric text-ink">{formatInr(quote.price)}</span>,{" "}
      {quote.alt.source.toUpperCase()} quotes{" "}
      <span className="numeric text-ink">{formatInr(quote.alt.price)}</span>.
      Treat the exact price as unsettled.
    </p>
  );
}
