"use client";

import { useEffect, useRef } from "react";
import type { Item } from "@/api/types";
import { useHistory } from "@/hooks/useHistory";
import { CatalystList } from "./CatalystList";
import { Decomposition } from "./Decomposition";
import { DisputedPrices, FreshnessBadge } from "./FreshnessBadge";
import { PeerPanel } from "./PeerPanel";
import { SignalList } from "./SignalChips";
import { Sparkline } from "./Sparkline";
import {
  formatInr,
  formatSignedPercent,
  stripSuffix,
} from "@/lib/format";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-line px-5 py-5 sm:px-6">
      <h3 className="mb-3 text-[11px] font-medium tracking-wide text-faint uppercase">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-raised px-3 py-2">
      <p className="text-[11px] text-faint">{label}</p>
      <p className="numeric mt-0.5 text-sm text-ink">{value}</p>
    </div>
  );
}

export function DetailDrawer({
  item,
  onClose,
}: {
  item: Item;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const { data: history, isPending: isHistoryPending } = useHistory(item.symbol);

  useEffect(() => {
    const restoreTo = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = overflow;
      restoreTo?.focus();
    };
  }, [onClose]);

  const toHigh =
    ((item.levels.high_52w - item.quote.price) / item.quote.price) * 100;
  const toLow =
    ((item.quote.price - item.levels.low_52w) / item.quote.price) * 100;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        aria-label="Close details"
        onClick={onClose}
        className="absolute inset-0 bg-black/65 backdrop-blur-[2px]"
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-label={`${stripSuffix(item.symbol)} details`}
        className="relative flex h-full w-full max-w-lg flex-col overflow-y-auto border-l border-line bg-surface"
      >
        <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-line bg-surface px-5 py-4 sm:px-6">
          <div className="min-w-0">
            <h2 className="numeric text-lg font-semibold text-ink">
              {stripSuffix(item.symbol)}
            </h2>
            <p className="truncate text-[13px] text-muted">{item.name}</p>
            <div className="mt-1.5 flex items-baseline gap-2.5">
              <span className="numeric text-sm text-ink">
                {formatInr(item.quote.price)}
              </span>
              <span
                className={`numeric text-sm ${item.today_change_pct >= 0 ? "text-up" : "text-down"}`}
              >
                {formatSignedPercent(item.today_change_pct)}
              </span>
              <FreshnessBadge quote={item.quote} />
            </div>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded-md border border-line px-2.5 py-1.5 text-xs text-muted transition-colors hover:border-line-strong hover:text-ink"
          >
            Close
          </button>
        </header>

        <div className="px-5 pt-5 sm:px-6">
          <Decomposition
            today={item.today_change_pct}
            peer={item.peer_change_pct}
            residual={item.residual_pct}
            peerHint={
              item.peer.method === "cluster"
                ? `${item.peer.size} behavioural peers did this too`
                : "Beta-adjusted Nifty move"
            }
          />
          <DisputedPrices quote={item.quote} />
        </div>

        <Section title="90 sessions">
          {isHistoryPending && <div className="skeleton h-32 rounded-lg" aria-hidden />}
          {history && <Sparkline history={history} />}
          <p className="mt-1 text-[11px] text-faint">
            Solid line is the close. Dashed line is the 20-day moving average.
          </p>
        </Section>

        <Section title="Where it sits">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Stat
              label="vs 20 DMA"
              value={formatSignedPercent(item.sma_distance_pct["20"], 1)}
            />
            <Stat
              label="vs 50 DMA"
              value={formatSignedPercent(item.sma_distance_pct["50"], 1)}
            />
            <Stat
              label="vs 200 DMA"
              value={formatSignedPercent(item.sma_distance_pct["200"], 1)}
            />
            <Stat
              label="Day range"
              value={`${formatInr(item.quote.day_low)} – ${formatInr(item.quote.day_high)}`}
            />
            <Stat label="52w high" value={formatInr(item.levels.high_52w)} />
            <Stat label="52w low" value={formatInr(item.levels.low_52w)} />
            <Stat
              label="Room to high / low"
              value={`${toHigh.toFixed(1)}% / ${toLow.toFixed(1)}%`}
            />
          </div>
        </Section>

        {item.signals.length > 0 && (
          <Section title="Why it surfaced">
            <SignalList signals={item.signals} />
          </Section>
        )}

        <Section title="Peer group">
          <PeerPanel symbol={item.symbol} />
        </Section>

        <Section title="Catalysts">
          <CatalystList symbol={item.symbol} />
        </Section>
      </div>
    </div>
  );
}
