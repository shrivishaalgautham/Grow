"use client";

import type { Attention, Item } from "@/api/types";
import { useCatalysts } from "@/hooks/useCatalysts";
import { formatClock, formatInr, formatSignedPercent, formatVolume, initials, stripSuffix } from "@/lib/format";
import { Decomposition } from "./Decomposition";
import { FreshnessTag } from "./FreshnessTag";
import { Icon } from "./Icon";
import { CatalystChip, SignalChip } from "./SignalChips";

const ATTENTION: Record<Attention, { text: string; classes: string } | null> = {
  high: { text: "Worth a look • High", classes: "bg-primary-container/20 text-on-primary-container" },
  notable: { text: "Notable", classes: "bg-surface-container text-secondary" },
  quiet: null,
};

export function StockCard({
  item,
  prefetchCatalysts,
  onOpen,
  onSeen,
  isSeenPending,
}: {
  item: Item;
  prefetchCatalysts: boolean;
  onOpen: () => void;
  onSeen: () => void;
  isSeenPending: boolean;
}) {
  const catalysts = useCatalysts(prefetchCatalysts ? item.symbol : null);
  const catalystStatus = catalysts.data?.status ?? item.catalyst_status;
  const isDisputed = item.quote.confidence === "disputed" && item.quote.alt !== null;
  const isUp = item.today_change_pct >= 0;
  const attention = ATTENTION[item.attention];

  return (
    <article className="bg-surface-container-lowest rounded-xl p-space-lg md:p-space-xl shadow-sm hover:shadow-md transition-all duration-200">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-space-md pb-space-md">
        <div className="flex items-center gap-space-md min-w-0">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center font-headline-md text-headline-md font-bold shrink-0 ${isUp ? "bg-primary/10 text-primary" : "bg-tertiary-fixed/30 text-tertiary"}`}>
            {initials(item.symbol)}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-space-sm flex-wrap">
              <h3 className="font-headline-md text-headline-md text-on-surface">{stripSuffix(item.symbol)}</h3>
              {isDisputed ? (
                <span className="px-space-sm py-space-2xs rounded-full bg-error-container text-on-error-container font-label-sm text-label-sm font-bold flex items-center gap-space-2xs">
                  <span className="w-1.5 h-1.5 rounded-full bg-error" />
                  Disputed price
                </span>
              ) : (
                attention && <span className={`px-space-sm py-space-2xs rounded-full font-label-sm text-label-sm font-bold ${attention.classes}`}>{attention.text}</span>
              )}
              {item.low_confidence && (
                <span className="px-space-sm py-space-2xs rounded-full bg-surface-container text-secondary font-label-sm text-label-sm">Low confidence</span>
              )}
            </div>
            <p className="font-body-sm text-body-sm text-secondary truncate">{item.name} • {item.industry}</p>
          </div>
        </div>
        <div className="flex items-end justify-between lg:justify-end gap-space-xl">
          {!isDisputed && <FreshnessTag quote={item.quote} />}
          <div className="text-right">
            {isDisputed && item.quote.alt ? (
              <>
                <div className="font-headline-md text-headline-md text-on-surface tabular">{formatInr(item.quote.price)} / {formatInr(item.quote.alt.price)}</div>
                <div className="font-label-sm text-label-sm text-tertiary font-semibold">Divergence: {item.quote.divergence_pct?.toFixed(2)}%</div>
              </>
            ) : (
              <>
                <div className="font-headline-md text-headline-md text-on-surface font-bold tabular">{formatInr(item.quote.price)}</div>
                <div className={`font-metric-tabular text-metric-tabular font-bold flex items-center justify-end gap-space-2xs ${isUp ? "text-primary" : "text-tertiary"}`}>
                  <Icon name={isUp ? "arrow_drop_up" : "arrow_drop_down"} size={16} />
                  {formatSignedPercent(item.today_change_pct)} today
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {isDisputed && item.quote.alt ? (
        <div className="p-space-md bg-error-container/25 rounded-xl flex items-start gap-space-md">
          <Icon name="sync_problem" size={22} className="text-error shrink-0 mt-space-2xs" />
          <div className="space-y-space-2xs">
            <div className="font-label-md text-label-md text-on-error-container font-bold">
              Disputed price: {item.quote.source.toUpperCase()} {formatInr(item.quote.price)} vs {item.quote.alt.source.toUpperCase()} {formatInr(item.quote.alt.price)} ({item.quote.divergence_pct?.toFixed(2)}% divergence).
            </div>
            <p className="font-body-sm text-body-sm text-on-surface-variant">
              No signals fire on disputed prices. Both quotes are shown and the fresher one is served until the two sources agree within 0.5%.
            </p>
          </div>
        </div>
      ) : (
        <Decomposition item={item} showRange={item.quote.confidence !== "closed"} />
      )}

      {item.low_confidence && (
        <p className="mt-space-sm px-space-md py-space-sm bg-surface-container-low rounded-lg font-body-sm text-body-sm text-secondary">
          This name trades thinly or has little history, so its volatility baseline is approximate and the engine suppresses live signals for it.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-space-sm py-space-xs">
        {item.signals.map((signal) => (
          <SignalChip key={`${signal.type}-${signal.trading_date}-${signal.rule_id ?? ""}`} signal={signal} />
        ))}
        <CatalystChip status={catalystStatus} headline={catalysts.data?.items[0]?.headline} />
      </div>

      <div className="mt-space-md pt-space-sm flex flex-col sm:flex-row sm:items-center justify-between gap-space-md">
        <div className="font-body-sm text-body-sm text-secondary font-mono">
          {isDisputed
            ? `Exchange mismatch flagged ${formatClock(item.quote.as_of)} IST`
            : `z ${item.z_score.toFixed(1)} • RVOL ${item.rvol.toFixed(1)}x${item.rvol_is_approximate ? "≈" : ""} • Vol ${formatVolume(item.quote.volume)}${
                item.change_since_seen_pct !== null ? ` • ${formatSignedPercent(item.change_since_seen_pct, 1)} since seen` : ""
              }`}
        </div>
        <div className="flex items-center gap-space-sm self-end sm:self-auto">
          <button type="button" onClick={onOpen} className="px-space-md py-space-xs bg-surface-container-low hover:bg-surface-container text-on-surface font-label-md text-label-md rounded-lg transition-colors">
            Details
          </button>
          <button
            type="button"
            onClick={onSeen}
            disabled={isSeenPending}
            className="px-space-md py-space-xs bg-surface-container-highest hover:bg-surface-container-high text-on-surface font-label-md text-label-md rounded-lg transition-colors flex items-center gap-space-2xs disabled:opacity-60"
          >
            <Icon name="check" size={16} className="text-primary" />
            <span>Got it</span>
          </button>
        </div>
      </div>
    </article>
  );
}
