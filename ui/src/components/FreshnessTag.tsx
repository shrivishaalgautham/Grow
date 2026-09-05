import type { Quote } from "@/api/types";
import { formatClock, formatStaleness } from "@/lib/format";

const DOTS: Record<Quote["confidence"], string> = {
  fresh: "bg-primary animate-ping",
  delayed: "bg-secondary",
  stale: "bg-outline",
  disputed: "bg-error",
  closed: "bg-secondary",
};

export function freshnessText(quote: Quote) {
  const source = quote.source.toUpperCase();
  switch (quote.confidence) {
    case "fresh":
      return `Fresh • Live ${formatClock(quote.as_of)} IST (${source})`;
    case "delayed":
      return `Delayed ${formatStaleness(quote.staleness_seconds)} • ${source}`;
    case "stale":
      return `Stale • last good ${formatStaleness(quote.staleness_seconds)} (${source})`;
    case "disputed":
      return `Disputed • ${source} vs ${quote.alt?.source.toUpperCase() ?? "alt"}`;
    case "closed":
      return `Closed • last traded ${formatClock(quote.as_of)} IST`;
  }
}

export function FreshnessTag({ quote, className = "" }: { quote: Quote; className?: string }) {
  return (
    <div className={`flex items-center gap-space-xs text-secondary font-label-sm text-label-sm ${className}`}>
      <span className={`w-2 h-2 rounded-full ${DOTS[quote.confidence]}`} />
      <span>{freshnessText(quote)}</span>
    </div>
  );
}
