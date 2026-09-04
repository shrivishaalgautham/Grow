"use client";

import type { Attention, Item } from "@/api/types";
import { Decomposition } from "./Decomposition";
import { DisputedPrices, FreshnessBadge } from "./FreshnessBadge";
import { SignalList } from "./SignalChips";
import {
  formatInr,
  formatSignedPercent,
  formatVolume,
  stripSuffix,
} from "@/lib/format";

const ACCENT: Record<Attention, string> = {
  high: "bg-high",
  notable: "bg-notable",
  quiet: "bg-line-strong",
};

const ATTENTION_LABEL: Record<Attention, string> = {
  high: "Worth a look",
  notable: "Notable",
  quiet: "Quiet",
};

export function StockCard({
  item,
  onOpen,
  onSeen,
  isSeenPending,
}: {
  item: Item;
  onOpen: () => void;
  onSeen: () => void;
  isSeenPending: boolean;
}) {
  const change = item.today_change_pct;

  return (
    <article className="relative overflow-hidden rounded-xl border border-line bg-surface">
      <span
        className={`absolute inset-y-0 left-0 w-[3px] ${ACCENT[item.attention]}`}
        aria-hidden
      />

      <div className="p-4 pl-5 sm:p-5 sm:pl-6">
        <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div className="min-w-0">
            <div className="flex items-baseline gap-2">
              <h3 className="numeric text-base font-semibold text-ink">
                {stripSuffix(item.symbol)}
              </h3>
              <span
                className={`text-[11px] font-medium tracking-wide uppercase ${item.attention === "high" ? "text-high" : "text-notable"}`}
              >
                {ATTENTION_LABEL[item.attention]}
              </span>
            </div>
            <p className="mt-0.5 truncate text-[13px] text-muted">
              {item.name}
              <span className="text-faint"> · {item.industry}</span>
            </p>
          </div>

          <div className="text-right">
            <p className="numeric text-base text-ink">
              {formatInr(item.quote.price)}
            </p>
            <p
              className={`numeric text-sm ${change >= 0 ? "text-up" : "text-down"}`}
            >
              {formatSignedPercent(change)}
            </p>
          </div>
        </header>

        <div className="mt-4 border-t border-line pt-4">
          <Decomposition
            today={item.today_change_pct}
            peer={item.peer_change_pct}
            residual={item.residual_pct}
          />
        </div>

        {item.signals.length > 0 && (
          <div className="mt-4 border-t border-line pt-4">
            <SignalList signals={item.signals} />
          </div>
        )}

        <DisputedPrices quote={item.quote} />

        {item.low_confidence && (
          <p className="mt-3 rounded-md border border-line bg-raised px-3 py-2 text-xs text-muted">
            Low confidence: this name trades thinly, so its volume baseline is
            approximate and the peer fit is weaker than usual.
          </p>
        )}

        <footer className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-faint">
            <FreshnessBadge quote={item.quote} />
            <span className="numeric">
              z {item.z_score.toFixed(2)} · rvol {item.rvol.toFixed(2)}
              {item.rvol_is_approximate && "≈"}
            </span>
            <span className="numeric">
              vol {formatVolume(item.quote.volume)}
            </span>
            {item.change_since_seen_pct !== null && (
              <span className="numeric">
                {formatSignedPercent(item.change_since_seen_pct)} since you
                looked
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onOpen}
              className="rounded-md border border-line px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:border-line-strong hover:text-ink"
            >
              Details
            </button>
            <button
              type="button"
              onClick={onSeen}
              disabled={isSeenPending}
              className="rounded-md bg-raised px-3 py-1.5 text-xs font-medium text-ink transition-colors hover:bg-line disabled:opacity-50"
            >
              Got it
            </button>
          </div>
        </footer>
      </div>
    </article>
  );
}
