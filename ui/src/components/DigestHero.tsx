"use client";

import Link from "next/link";
import type { BriefingOut, DigestOut } from "@/api/types";
import { formatAwayDuration, formatDay } from "@/lib/format";
import { Icon } from "./Icon";

function headline(digest: DigestOut) {
  const { changed_count, total_count, away_duration_seconds } = digest;
  const stocks = `${total_count} stock${total_count === 1 ? "" : "s"}`;
  if (total_count === 0) return "Your watchlist is empty.";
  if (away_duration_seconds === null) {
    return `First look — ${changed_count} of ${stocks} ${changed_count === 1 ? "is" : "are"} doing something the market is not.`;
  }
  if (changed_count === 0) {
    return `You were away ${formatAwayDuration(away_duration_seconds)} and nothing in your ${stocks} moved beyond its own noise.`;
  }
  return `You were away ${formatAwayDuration(away_duration_seconds)} — ${changed_count} of ${stocks} did something.`;
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
    <section className="bg-surface-container-lowest rounded-xl p-space-xl md:p-space-2xl shadow-sm relative overflow-hidden">
      <div className="absolute -right-16 -top-16 w-80 h-80 rounded-full bg-primary-container/10 pointer-events-none blur-3xl" />
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-space-lg relative z-10">
        <div className="max-w-3xl space-y-space-sm">
          <div className="flex items-center gap-space-xs">
            <Icon name="auto_awesome" size={20} className="text-primary" />
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-primary font-bold">Briefing since your last review</span>
          </div>
          <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">{headline(digest)}</h1>
          <div className="flex items-center gap-space-xs text-secondary font-label-sm text-label-sm flex-wrap">
            <span>Bars through {formatDay(digest.latest_bar_date)}</span>
            {briefing && (
              <>
                <span>•</span>
                <span>
                  {briefing.source === "llm" ? "Written by a model" : "Assembled from a template"}
                  {briefing.was_cached ? " (cached)" : ""}
                </span>
              </>
            )}
          </div>
          {isBriefingLoading && (
            <div className="space-y-2 pt-space-xs" aria-hidden>
              <div className="skeleton h-4 w-full" />
              <div className="skeleton h-4 w-[92%]" />
              <div className="skeleton h-4 w-[70%]" />
            </div>
          )}
          {briefing && (
            <p className="font-body-lg text-body-lg text-on-surface-variant pt-space-xs leading-relaxed">{briefing.text}</p>
          )}
          {digest.total_count === 0 && (
            <p className="font-body-lg text-body-lg text-on-surface-variant pt-space-xs">
              Add a few symbols below and the next load tells you which of them moved for their own reasons rather than the market&rsquo;s.
            </p>
          )}
          {digest.total_count > 0 && (
            <div className="pt-space-xs">
              <Link href="/evidence" className="inline-flex items-center gap-space-2xs font-label-lg text-label-lg text-primary hover:text-on-primary-container transition-colors">
                <span>Why you&rsquo;re seeing {digest.changed_count} and not every 2% move (Evidence)</span>
                <Icon name="arrow_forward" size={16} />
              </Link>
            </div>
          )}
        </div>
        {digest.changed_count > 0 && (
          <div className="flex flex-col sm:flex-row md:flex-col items-stretch sm:items-center md:items-end gap-space-sm self-start md:self-auto shrink-0">
            <button
              type="button"
              onClick={onMarkAll}
              disabled={isMarkAllPending}
              className="px-space-xl py-space-sm bg-primary-container hover:bg-primary-fixed-dim text-on-primary-fixed font-label-lg text-label-lg rounded-lg shadow-sm transition-all duration-150 flex items-center justify-center gap-space-xs disabled:opacity-60"
            >
              <Icon name="done_all" size={18} />
              <span>Mark all reviewed</span>
            </button>
            <span className="font-label-sm text-label-sm text-secondary text-center md:text-right">
              Clears {digest.changed_count} unread {digest.changed_count === 1 ? "alert" : "alerts"}
            </span>
          </div>
        )}
      </div>
    </section>
  );
}
