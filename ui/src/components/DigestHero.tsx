"use client";

import type { BriefingOut, DigestOut } from "@/api/types";
import { formatAwayDuration, formatDay } from "@/lib/format";

function Headline({ digest }: { digest: DigestOut }) {
  const { changed_count, total_count, away_duration_seconds } = digest;
  const stocks = `${total_count} stock${total_count === 1 ? "" : "s"}`;

  if (total_count === 0) {
    return <>Your watchlist is empty.</>;
  }
  if (away_duration_seconds === null) {
    return (
      <>
        First look — {changed_count} of {stocks}{" "}
        {changed_count === 1 ? "is" : "are"} doing something the market is not.
      </>
    );
  }
  if (changed_count === 0) {
    return (
      <>
        You were away {formatAwayDuration(away_duration_seconds)} and nothing in
        your {stocks} moved beyond its own noise.
      </>
    );
  }
  return (
    <>
      You were away {formatAwayDuration(away_duration_seconds)} —{" "}
      <span className="text-high">{changed_count}</span> of {stocks} did
      something.
    </>
  );
}

export function DigestHero({
  digest,
  briefing,
  isBriefingLoading,
  onMarkAll,
  isMarkAllPending,
}: {
  digest: DigestOut;
  briefing: BriefingOut | undefined;
  isBriefingLoading: boolean;
  onMarkAll: () => void;
  isMarkAllPending: boolean;
}) {
  return (
    <section className="rounded-xl border border-line bg-surface p-5 sm:p-7">
      <h2 className="text-xl leading-snug font-semibold text-balance text-ink sm:text-2xl">
        <Headline digest={digest} />
      </h2>

      {digest.total_count === 0 && (
        <p className="mt-4 max-w-[68ch] text-[15px] leading-relaxed text-muted">
          Add a few symbols and the next load will tell you which of them moved
          for their own reasons rather than the market&rsquo;s.
        </p>
      )}

      {isBriefingLoading && (
        <div className="mt-4 space-y-2" aria-hidden>
          <div className="skeleton h-3.5 w-full rounded" />
          <div className="skeleton h-3.5 w-[92%] rounded" />
          <div className="skeleton h-3.5 w-[70%] rounded" />
        </div>
      )}

      {briefing && (
        <p className="mt-4 max-w-[68ch] text-[15px] leading-relaxed text-muted">
          {briefing.text}
        </p>
      )}

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
        <p className="text-[11px] text-faint">
          Bars through {formatDay(digest.latest_bar_date)}
          {briefing &&
            ` · briefing ${briefing.source === "llm" ? "written by a model" : "assembled from a template"}${briefing.was_cached ? ", cached" : ""}`}
        </p>

        {digest.changed_count > 0 && (
          <button
            type="button"
            onClick={onMarkAll}
            disabled={isMarkAllPending}
            className="rounded-md bg-ink px-3.5 py-2 text-xs font-semibold text-canvas transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            Mark all reviewed
          </button>
        )}
      </div>
    </section>
  );
}
