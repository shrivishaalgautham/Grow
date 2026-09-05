"use client";

import { ApiError } from "@/api/errors";
import type { ExplanationSource } from "@/api/types";
import { useCatalysts } from "@/hooks/useCatalysts";
import { useExplanation } from "@/hooks/useExplanation";
import { formatRelative } from "@/lib/format";
import { Icon } from "./Icon";

const EXPLANATION_SOURCE_LABEL: Record<ExplanationSource, string> = {
  llm_grounded: "Written by a model, grounded in a live web search",
  llm: "Written by a model from the facts and headlines",
  template: "Assembled from the facts",
};

const SOURCE_LABEL: Record<string, string> = {
  nse: "NSE announcement",
  yahoo_rss: "Yahoo Finance",
  google_news: "Google News",
  gdelt: "GDELT",
};

const STATUS_LABEL = {
  found: "Status: found",
  none_found: "Status: none found",
  pending: "Status: looking…",
  unavailable: "Status: unavailable",
} as const;

export function CatalystPanel({ symbol }: { symbol: string }) {
  const { data, isPending, error } = useCatalysts(symbol);
  const isNotSurfaced = error instanceof ApiError && error.code === "not_surfaced";
  const explanation = useExplanation(isNotSurfaced ? null : symbol);

  return (
    <div className="space-y-space-md">
      <div className="flex items-center justify-between gap-space-md">
        <div className="flex items-center gap-space-xs">
          <span className="font-headline-sm text-headline-sm text-on-surface">Catalysts</span>
          {data && (
            <span className={`px-space-xs py-space-2xs font-label-sm text-label-sm rounded uppercase font-bold ${data.status === "none_found" ? "bg-tertiary-fixed/40 text-on-tertiary-fixed" : "bg-secondary-container text-on-secondary-fixed"}`}>
              {STATUS_LABEL[data.status]}
            </span>
          )}
        </div>
        <span className="font-body-sm text-body-sm text-secondary">NSE filings • Google News • GDELT • Yahoo</span>
      </div>

      {isPending && <div className="skeleton h-16" aria-hidden />}

      {!isNotSurfaced && (
        <div className="p-space-md bg-surface-container-low rounded-lg">
          <div className="flex items-center justify-between gap-space-sm mb-space-xs">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-primary font-bold flex items-center gap-space-2xs">
              <Icon name="auto_awesome" size={16} />
              What happened, in plain words
            </span>
            {explanation.data?.status === "ready" && (
              <span className="font-label-sm text-label-sm text-secondary">
                {explanation.data.source ? EXPLANATION_SOURCE_LABEL[explanation.data.source] : ""}
                {explanation.data.was_cached ? " • cached" : ""}
              </span>
            )}
          </div>
          {(explanation.isPending || explanation.data?.status === "pending") && (
            <div className="space-y-2" aria-hidden>
              <div className="skeleton h-3.5 w-full" />
              <div className="skeleton h-3.5 w-[80%]" />
            </div>
          )}
          {explanation.data?.status === "ready" && (
            <p className="font-body-md text-body-md text-on-surface leading-relaxed">{explanation.data.text}</p>
          )}
          {explanation.isError && (
            <p className="font-body-sm text-body-sm text-secondary">The explanation could not be generated right now.</p>
          )}
        </div>
      )}

      {isNotSurfaced && (
        <p className="font-body-sm text-body-sm text-secondary">
          News is only fetched for stocks that actually moved, so nothing was requested for this one.
        </p>
      )}
      {error && !isNotSurfaced && <p className="font-body-sm text-body-sm text-tertiary">News could not be loaded right now.</p>}

      {data?.status === "pending" && (
        <p className="font-body-sm text-body-sm text-secondary flex items-center gap-space-xs">
          <Icon name="progress_activity" size={16} className="animate-spin text-primary" /> Looking for a catalyst… this checks once more in a few seconds.
        </p>
      )}
      {data?.status === "none_found" && (
        <div className="p-space-md bg-tertiary-fixed/30 rounded-lg flex items-start gap-space-sm">
          <Icon name="search_off" size={20} className="text-tertiary shrink-0" />
          <p className="font-body-sm text-body-sm text-on-surface">
            <strong>No public catalyst found.</strong> The move is real and peer-adjusted, but no filing or headline explains it. That is itself worth knowing.
          </p>
        </div>
      )}
      {data?.status === "unavailable" && (
        <div className="p-space-md bg-surface-container-low rounded-lg flex items-start gap-space-sm">
          <Icon name="cloud_off" size={20} className="text-secondary shrink-0" />
          <p className="font-body-sm text-body-sm text-on-surface">
            The news sources refused the request. Absence of headlines here means the fetch failed, not that nothing happened.
          </p>
        </div>
      )}
      {data?.status === "found" &&
        data.items.map((catalyst) => (
          <a
            key={catalyst.url + catalyst.headline}
            href={catalyst.url || undefined}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="block group p-space-md bg-surface-container-low hover:bg-surface-container transition-colors rounded-lg"
          >
            <div className="flex items-start justify-between gap-space-md">
              <div className="min-w-0">
                <h4 className="font-headline-sm text-headline-sm text-on-surface group-hover:text-primary transition-colors leading-snug">{catalyst.headline}</h4>
                <div className="flex items-center gap-space-xs mt-space-xs font-body-sm text-body-sm text-secondary">
                  <span>{SOURCE_LABEL[catalyst.source] ?? catalyst.source}</span>
                  {catalyst.published_at && (
                    <>
                      <span>•</span>
                      <span>{formatRelative(catalyst.published_at)}</span>
                    </>
                  )}
                </div>
              </div>
              <Icon name="open_in_new" size={20} className="text-secondary group-hover:text-primary transition-colors shrink-0" />
            </div>
          </a>
        ))}

      <div className="flex items-center gap-space-xs p-space-sm bg-surface-container-low/60 rounded-lg text-secondary font-body-sm text-body-sm">
        <Icon name="verified" size={18} className="text-primary shrink-0" />
        <span>
          Events explain, they never score. Headlines are searched only for stocks that surfaced, and the model treats them as untrusted data: it may say a move coincided with a headline, never that it happened because of one.
        </span>
      </div>
    </div>
  );
}
