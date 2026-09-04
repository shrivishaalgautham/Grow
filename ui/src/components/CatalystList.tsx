"use client";

import { ApiError } from "@/api/errors";
import { useCatalysts } from "@/hooks/useCatalysts";
import { formatTime } from "@/lib/format";

function Note({ children }: { children: string }) {
  return <p className="text-[13px] leading-relaxed text-faint">{children}</p>;
}

export function CatalystList({ symbol }: { symbol: string }) {
  const { data, isPending, error } = useCatalysts(symbol);

  if (isPending) return <div className="skeleton h-16 rounded-lg" aria-hidden />;

  if (error) {
    const notSurfaced =
      error instanceof ApiError && error.code === "not_surfaced";
    return (
      <Note>
        {notSurfaced
          ? "News is only fetched for stocks that actually moved, so nothing was requested for this one."
          : "News could not be loaded right now."}
      </Note>
    );
  }

  if (data.status === "pending") {
    return <Note>Looking for a catalyst…</Note>;
  }
  if (data.status === "none_found") {
    return (
      <Note>
        No catalyst found. The move is real and peer-adjusted, but no filing or
        headline explains it — which is itself worth knowing.
      </Note>
    );
  }
  if (data.status === "unavailable") {
    return (
      <Note>
        The news source refused the request. Absence of headlines here means the
        fetch failed, not that nothing happened.
      </Note>
    );
  }

  return (
    <ul className="space-y-2.5">
      {data.items.map((catalyst) => (
        <li key={catalyst.url + catalyst.headline}>
          <a
            href={catalyst.url}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="block rounded-md border border-line bg-raised px-3 py-2.5 transition-colors hover:border-line-strong"
          >
            <p className="text-[13px] leading-snug text-ink">
              {catalyst.headline}
            </p>
            <p className="mt-1 text-[11px] text-faint">
              {catalyst.source}
              {catalyst.published_at && ` · ${formatTime(catalyst.published_at)}`}
            </p>
          </a>
        </li>
      ))}
    </ul>
  );
}
