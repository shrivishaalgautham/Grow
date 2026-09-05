"use client";

import { isRateLimited, isSessionGone } from "@/api/errors";
import type { DigestOut } from "@/api/types";
import { formatDay, formatRetryAfter } from "@/lib/format";
import { Icon } from "./Icon";
import type { IconName } from "./icons";

type Tone = "neutral" | "warn" | "info";

const TONES: Record<Tone, string> = {
  neutral: "bg-surface-container-low",
  warn: "bg-tertiary-fixed/40",
  info: "bg-surface-container-high",
};

function Banner({
  tone = "neutral",
  icon,
  title,
  detail,
  badge,
  action,
}: {
  tone?: Tone;
  icon?: IconName;
  title: string;
  detail?: string;
  badge?: string;
  action?: React.ReactNode;
}) {
  return (
    <div role="status" className={`${TONES[tone]} px-space-md py-space-sm rounded-xl flex items-center justify-between gap-space-md shadow-sm`}>
      <div className="flex items-center gap-space-sm min-w-0">
        {icon ? (
          <Icon name={icon} size={18} className={tone === "warn" ? "text-tertiary" : "text-primary"} />
        ) : (
          <span className="w-2.5 h-2.5 rounded-full bg-secondary shrink-0" />
        )}
        <span className="font-label-md text-label-md text-on-surface">{title}</span>
        {detail && <span className="text-secondary font-body-sm text-body-sm hidden md:inline">• {detail}</span>}
      </div>
      {badge && (
        <span className="font-label-sm text-label-sm text-secondary tracking-wider uppercase bg-surface-container px-space-sm py-space-2xs rounded shrink-0">
          {badge}
        </span>
      )}
      {action}
    </div>
  );
}

export function Banners({
  digest,
  error,
  onRetry,
  briefingError,
}: {
  digest: DigestOut | undefined;
  error: Error | null;
  onRetry: () => void;
  briefingError: Error | null;
}) {
  return (
    <section className="flex flex-col gap-space-xs">
      {isSessionGone(error) && (
        <Banner tone="warn" icon="lock_reset" title="Your session expired" detail="Returning to the start page" />
      )}
      {isRateLimited(error) && (
        <Banner
          tone="warn"
          icon="speed"
          title="Too many requests"
          detail={`Retry in ${formatRetryAfter(error.retryAfterSeconds ?? 60)}`}
        />
      )}
      {error && !isSessionGone(error) && !isRateLimited(error) && (
        <Banner
          tone="warn"
          icon="cloud_off"
          title="Could not load your watchlist"
          detail="The API did not respond. Your watchlist and seen-state are untouched."
          action={
            <button type="button" onClick={onRetry} className="font-label-sm text-label-sm text-primary hover:underline font-bold shrink-0">
              Try again
            </button>
          }
        />
      )}
      {isRateLimited(briefingError) && (
        <Banner
          tone="warn"
          icon="speed"
          title="Briefing is rate limited"
          detail={`The digest below is unaffected. Retry in ${formatRetryAfter(briefingError.retryAfterSeconds ?? 60)}`}
        />
      )}
      {digest?.replay_date && (
        <Banner
          tone="info"
          icon="history_toggle_off"
          title={`Clock pinned to ${formatDay(digest.replay_date)} for rehearsal`}
          detail="Real bars from that session, not live prices"
          badge="Replay"
        />
      )}
      {digest?.providers_degraded && (
        <Banner
          tone="warn"
          icon="warning"
          title="Price providers degraded; last known good quotes served"
          detail="Signals still come from real bars; only the prices are behind"
          badge="Failover"
        />
      )}
    </section>
  );
}
