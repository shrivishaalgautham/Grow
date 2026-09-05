"use client";

import { useEffect, useRef } from "react";
import type { Item } from "@/api/types";
import { useHistory } from "@/hooks/useHistory";
import { formatInr, formatSignedPercent, stripSuffix } from "@/lib/format";
import { CatalystPanel } from "./CatalystPanel";
import { peerLabel } from "./Decomposition";
import { FreshnessTag } from "./FreshnessTag";
import { Icon } from "./Icon";
import { PeerPanel } from "./PeerPanel";
import { PriceChart } from "./PriceChart";
import { SIGNAL_NAMES } from "./SignalChips";

const tone = (value: number) => (value > 0 ? "text-primary" : value < 0 ? "text-tertiary" : "text-on-surface");

function lastValue(series: (number | null)[]) {
  for (let index = series.length - 1; index >= 0; index -= 1) {
    const value = series[index];
    if (value !== null) return value;
  }
  return null;
}

function DecompositionPill({ label, value, hint, share, emphasis }: { label: string; value: number; hint: string; share: number; emphasis?: boolean }) {
  return (
    <div className="bg-surface-container-lowest p-space-md rounded-lg shadow-sm relative overflow-hidden">
      {emphasis && <div className="absolute top-0 right-0 w-12 h-12 bg-primary/10 rounded-bl-full pointer-events-none" />}
      <span className={`font-label-sm text-label-sm block mb-space-2xs ${emphasis ? "text-primary font-semibold" : "text-secondary"}`}>{label}</span>
      <div className="flex items-baseline gap-space-xs">
        <span className={`font-headline-md text-headline-md tabular ${emphasis ? "font-bold" : ""} ${tone(value)}`}>{formatSignedPercent(value)}</span>
        <span className="font-body-sm text-body-sm text-secondary">({hint})</span>
      </div>
      <div className="w-full bg-surface-container-high h-1.5 rounded-full mt-space-sm overflow-hidden">
        <div className={`h-full rounded-full ${emphasis ? "bg-primary-container" : value >= 0 ? "bg-primary" : "bg-tertiary"}`} style={{ width: `${Math.max(3, share)}%` }} />
      </div>
    </div>
  );
}

function RangeSlider({ low, high, value, lowLabel, highLabel, middle, tone: barTone }: { low: number; high: number; value: number; lowLabel: string; highLabel: string; middle: string; tone: string }) {
  const span = high - low;
  const position = span <= 0 ? 50 : Math.max(0, Math.min(100, ((value - low) / span) * 100));
  return (
    <div>
      <div className="flex items-center justify-between text-secondary font-body-sm text-body-sm mb-space-2xs gap-space-sm">
        <div><span className="text-on-surface-variant font-medium">{lowLabel}:</span> {formatInr(low)}</div>
        <div className="font-label-sm text-label-sm text-primary font-bold text-center">{middle}</div>
        <div><span className="text-on-surface-variant font-medium">{highLabel}:</span> {formatInr(high)}</div>
      </div>
      <div className="relative w-full h-2 bg-surface-container-high rounded-full overflow-visible">
        <div className={`absolute top-0 bottom-0 left-0 rounded-full ${barTone}`} style={{ width: `${position}%` }} />
        <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 bg-on-surface rounded-full shadow" style={{ left: `${position}%` }} />
      </div>
    </div>
  );
}

export function DetailDrawer({
  item,
  onClose,
  onSeen,
  onRemove,
  isSeenPending,
}: {
  item: Item;
  onClose: () => void;
  onSeen: () => void;
  onRemove: () => void;
  isSeenPending: boolean;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const history = useHistory(item.symbol);

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

  const changeInr = item.quote.price - item.quote.prev_close;
  const isUp = item.today_change_pct >= 0;
  const magnitudes = [item.today_change_pct, item.peer_change_pct, item.residual_pct].map(Math.abs);
  const maxMagnitude = Math.max(0.01, ...magnitudes);
  const share = (value: number) => (Math.abs(value) / maxMagnitude) * 100;
  const dma = {
    "20": history.data ? lastValue(history.data.sma["20"]) : null,
    "50": history.data ? lastValue(history.data.sma["50"]) : null,
    "200": history.data ? lastValue(history.data.sma["200"]) : null,
  };
  const roomToHigh = ((item.levels.high_52w - item.quote.price) / item.quote.price) * 100;

  return (
    <div className="fixed inset-0 z-50">
      <button type="button" aria-label="Close details" onClick={onClose} className="absolute inset-0 bg-on-surface/30 backdrop-blur-[3px]" />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={`${stripSuffix(item.symbol)} details`}
        className="absolute top-0 right-0 h-full w-full sm:w-[680px] lg:w-[740px] bg-surface-container-lowest shadow-2xl flex flex-col overflow-hidden"
      >
        <div className="flex-shrink-0 bg-surface-container-lowest px-space-xl pt-space-xl pb-space-md shadow-sm relative">
          <div className="flex items-start justify-between gap-space-md mb-space-sm">
            <div className="min-w-0">
              <div className="flex items-center gap-space-sm flex-wrap">
                <span className="font-headline-lg text-headline-lg text-on-surface tracking-tight">{stripSuffix(item.symbol)}</span>
                <span className="bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm px-space-xs py-space-2xs rounded">NSE</span>
                <span className="font-body-sm text-body-sm text-secondary truncate">{item.name} • {item.industry}</span>
              </div>
              <div className="flex items-baseline gap-space-md mt-space-xs">
                <span className="font-metric-display text-metric-display text-on-surface tabular">{formatInr(item.quote.price)}</span>
                <div className={`flex items-center gap-space-2xs font-metric-tabular text-metric-tabular ${isUp ? "text-primary" : "text-tertiary"}`}>
                  <Icon name={isUp ? "arrow_drop_up" : "arrow_drop_down"} size={18} />
                  <span>{formatSignedPercent(item.today_change_pct)} ({changeInr >= 0 ? "+" : "−"}{formatInr(Math.abs(changeInr))} today)</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-space-xs flex-shrink-0">
              {item.is_changed && (
                <button type="button" onClick={onSeen} disabled={isSeenPending} className="hidden sm:inline-flex items-center gap-space-xs bg-surface-container-low hover:bg-surface-container-high px-space-md py-space-xs rounded-lg font-label-md text-label-md text-on-surface transition-colors disabled:opacity-60">
                  <Icon name="done_all" size={16} className="text-primary" />
                  <span>Got it</span>
                </button>
              )}
              <button ref={closeRef} type="button" onClick={onClose} title="Close (Esc)" className="w-9 h-9 rounded-lg bg-surface-container-low hover:bg-surface-container-high flex items-center justify-center text-on-surface-variant hover:text-on-surface transition-colors">
                <Icon name="close" size={20} />
              </button>
            </div>
          </div>
          <div className="flex items-center gap-space-sm flex-wrap pt-space-xs">
            <div className="inline-flex items-center gap-space-xs bg-secondary-container/60 px-space-sm py-space-2xs rounded-full">
              <FreshnessTag quote={item.quote} className="text-on-secondary-fixed" />
            </div>
            {item.quote.alt && item.quote.divergence_pct !== null && (
              <span className="text-tertiary font-label-sm text-label-sm">
                {item.quote.alt.source.toUpperCase()} quotes {formatInr(item.quote.alt.price)} ({item.quote.divergence_pct.toFixed(2)}% apart)
              </span>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-space-xl py-space-lg space-y-space-xl">
          <div className="bg-surface-container-low p-space-md rounded-xl">
            <div className="flex items-center justify-between mb-space-sm">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-secondary">Return decomposition</span>
              <span className="font-body-sm text-body-sm text-secondary">{item.peer.method === "cluster" ? `Relative to a ${item.peer.size}-stock behavioural cluster` : "Relative to beta-adjusted Nifty"}</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-space-sm">
              <DecompositionPill label="Total return today" value={item.today_change_pct} hint="gross" share={share(item.today_change_pct)} />
              <DecompositionPill label={peerLabel(item)} value={item.peer_change_pct} hint="systematic" share={share(item.peer_change_pct)} />
              <DecompositionPill label="Stock-specific residual" value={item.residual_pct} hint={`z ${item.z_score.toFixed(1)}`} share={share(item.residual_pct)} emphasis />
            </div>
          </div>

          <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-space-sm mb-space-md">
              <div>
                <span className="font-headline-sm text-headline-sm text-on-surface">90 sessions</span>
                <p className="font-body-sm text-body-sm text-secondary">Close against moving averages, with each day&rsquo;s stock-specific residual as bars</p>
              </div>
              <div className="flex flex-wrap items-center gap-space-md text-secondary font-label-sm text-label-sm">
                <div className="flex items-center gap-space-2xs"><span className="w-3 h-0.5 bg-primary inline-block" /><span>Close</span></div>
                <div className="flex items-center gap-space-2xs"><span className="w-2.5 h-2 bg-primary-container/70 inline-block rounded-xs" /><span>Residual</span></div>
                <div className="flex items-center gap-space-2xs"><span className="w-3 border-t border-dashed border-primary" /><span>20-DMA{dma["20"] !== null ? ` (${formatInr(dma["20"])})` : ""}</span></div>
                <div className="flex items-center gap-space-2xs"><span className="w-3 border-t border-dashed border-secondary" /><span>50-DMA{dma["50"] !== null ? ` (${formatInr(dma["50"])})` : ""}</span></div>
              </div>
            </div>
            <div className="relative w-full overflow-hidden bg-surface-container-low/40 rounded-lg p-space-sm">
              {history.isPending && <div className="skeleton h-56" aria-hidden />}
              {history.isError && <p className="font-body-sm text-body-sm text-tertiary p-space-md">History could not be loaded.</p>}
              {history.data && <PriceChart history={history.data} levels={item.levels} price={item.quote.price} todayChangePct={item.today_change_pct} />}
            </div>
          </div>

          <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm space-y-space-md">
            <span className="font-headline-sm text-headline-sm text-on-surface block">Where it sits</span>
            <div className="grid grid-cols-3 gap-space-sm text-center">
              {(["20", "50", "200"] as const).map((window) => (
                <div key={window} className="bg-surface-container-low p-space-sm rounded-lg">
                  <span className="font-label-sm text-label-sm text-secondary block">vs {window}-DMA{dma[window] !== null ? ` (${formatInr(dma[window] as number)})` : ""}</span>
                  <span className={`font-headline-sm text-headline-sm tabular ${tone(item.sma_distance_pct[window])}`}>{formatSignedPercent(item.sma_distance_pct[window], 1)}</span>
                  <span className="font-body-sm text-body-sm text-secondary block">{item.sma_distance_pct[window] >= 0 ? "Above" : "Below"} the average</span>
                </div>
              ))}
            </div>
            <div className="space-y-space-md pt-space-xs">
              <RangeSlider low={item.quote.day_low} high={item.quote.day_high} value={item.quote.price} lowLabel="Day low" highLabel="Day high" middle={`LTP ${formatInr(item.quote.price)}`} tone="bg-primary-container" />
              <RangeSlider low={item.levels.low_52w} high={item.levels.high_52w} value={item.quote.price} lowLabel="52W low" highLabel="52W high" middle={`${roomToHigh.toFixed(1)}% room to the 52-week high`} tone="bg-secondary" />
            </div>
          </div>

          {item.signals.length > 0 && (
            <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm">
              <div className="flex items-center justify-between mb-space-md">
                <div className="flex items-center gap-space-xs">
                  <span className="font-headline-sm text-headline-sm text-on-surface">Why it surfaced</span>
                  <Icon name="auto_graph" size={18} className="text-primary" />
                </div>
                <span className="font-label-sm text-label-sm text-secondary">{item.signals.length} {item.signals.length === 1 ? "signal" : "signals"} since you looked</span>
              </div>
              <div className="space-y-space-sm">
                {item.signals.map((signal) => (
                  <div key={`${signal.type}-${signal.trading_date}-${signal.rule_id ?? ""}`} className="flex items-start gap-space-md p-space-md rounded-lg bg-surface-container-low/70">
                    <span className="px-space-sm py-space-2xs rounded-full font-label-sm text-label-sm uppercase tracking-wide bg-secondary-container text-primary font-bold flex-shrink-0" title={SIGNAL_NAMES[signal.type]}>
                      {signal.type}
                    </span>
                    <div className="min-w-0">
                      <p className="font-label-md text-label-md text-on-surface">{signal.headline}</p>
                      <p className="font-body-sm text-body-sm text-on-surface-variant mt-space-2xs">{signal.detail} <span className="text-secondary">({signal.trading_date})</span></p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm">
            <PeerPanel symbol={item.symbol} />
          </div>

          <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm">
            <CatalystPanel symbol={item.symbol} />
          </div>
        </div>

        <div className="flex-shrink-0 bg-surface-container-lowest px-space-xl py-space-md shadow-[0_-4px_16px_rgba(15,23,42,0.04)] flex items-center justify-between gap-space-md">
          <div className="flex items-center gap-space-sm flex-wrap">
            {item.is_changed && (
              <button type="button" onClick={onSeen} disabled={isSeenPending} className="inline-flex items-center justify-center gap-space-xs bg-primary-container text-on-primary-container hover:brightness-105 active:scale-[0.98] font-label-lg text-label-lg px-space-xl py-space-md rounded-lg shadow-sm transition-all disabled:opacity-60">
                <Icon name="task_alt" size={20} />
                <span>Got it (mark reviewed)</span>
              </button>
            )}
            <button type="button" onClick={onRemove} className="inline-flex items-center justify-center gap-space-xs bg-surface-container-low hover:bg-error-container hover:text-on-error-container font-label-lg text-label-lg text-on-surface-variant px-space-md py-space-md rounded-lg transition-colors">
              <Icon name="playlist_remove" size={18} />
              <span>Remove from watchlist</span>
            </button>
          </div>
          <span className="hidden sm:inline font-label-sm text-label-sm text-secondary">
            Press <kbd className="px-1.5 py-0.5 bg-surface-container-high rounded text-on-surface">Esc</kbd> to close
          </span>
        </div>
      </aside>
    </div>
  );
}
