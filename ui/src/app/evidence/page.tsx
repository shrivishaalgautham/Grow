"use client";

import Link from "next/link";
import { useState } from "react";
import type { EvidenceOut } from "@/api/types";
import { AppHeader } from "@/components/AppHeader";
import { Icon } from "@/components/Icon";
import { SiteFooter } from "@/components/SiteFooter";
import { useEvidence } from "@/hooks/useEvidence";
import { useSession } from "@/hooks/useSession";
import { formatClock, formatDay, formatSignedPercent, initials, stripSuffix } from "@/lib/format";

const WINDOWS = [30, 90, 180] as const;

function Bar({ index, title, badge, alerts, days, max, description, tone, isHighlighted }: { index: number; title: string; badge: string; alerts: number; days: number; max: number; description: string; tone: string; isHighlighted?: boolean }) {
  return (
    <div className={`rounded-xl p-space-lg transition-colors ${isHighlighted ? "bg-primary-container/10 ring-1 ring-primary-container/30" : "bg-surface-container-low/60 hover:bg-surface-container-low"}`}>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-space-xs mb-space-xs">
        <div className="flex items-center gap-space-sm">
          <span className={`font-headline-sm text-headline-sm ${isHighlighted ? "text-primary font-bold flex items-center gap-space-2xs" : "text-on-surface"}`}>
            {isHighlighted && <Icon name="auto_graph" size={18} className="text-primary" />}
            {index}. {title}
          </span>
          <span className={`px-space-xs py-space-2xs rounded font-label-sm text-label-sm ${isHighlighted ? "rounded-full bg-primary-container text-on-primary-container font-bold" : "bg-surface-container-high text-on-surface-variant"}`}>{badge}</span>
        </div>
        <div className="text-right">
          <span className={`font-metric-display text-headline-md font-bold tabular ${isHighlighted ? "text-primary" : "text-secondary"}`}>{alerts.toLocaleString("en-IN")} alerts</span>
          <span className={`font-body-sm text-body-sm ml-space-xs ${isHighlighted ? "text-primary font-semibold" : "text-secondary"}`}>({(alerts / days).toFixed(2)}/day)</span>
        </div>
      </div>
      <div className="w-full bg-surface-container h-3.5 rounded-full overflow-hidden my-space-xs">
        <div className={`${tone} h-full rounded-full transition-all duration-700 ease-out`} style={{ width: `${max === 0 ? 0 : (alerts / max) * 100}%` }} />
      </div>
      <p className={`font-body-sm text-body-sm mt-space-2xs ${isHighlighted ? "text-on-primary-container" : "text-on-surface-variant"}`}>{description}</p>
    </div>
  );
}

function SuppressedCard({ index, count, total, title, description }: { index: number; count: number; total: number; title: string; description: string }) {
  const pct = total === 0 ? 0 : Math.round((count / total) * 100);
  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-sm p-space-xl flex flex-col justify-between hover:shadow-md transition-shadow">
      <div>
        <div className="flex items-center justify-between mb-space-md">
          <span className="px-space-sm py-space-2xs rounded-full bg-secondary-container text-on-secondary-container font-label-sm text-label-sm font-bold">REASON 0{index}</span>
          <span className="font-label-lg text-label-lg text-secondary font-bold">{pct}%</span>
        </div>
        <div className="flex items-baseline gap-space-xs mb-space-2xs">
          <span className="font-metric-display text-metric-display text-on-surface font-bold tabular">{count.toLocaleString("en-IN")}</span>
          <span className="font-body-md text-body-md text-secondary">alerts suppressed</span>
        </div>
        <h3 className="font-headline-sm text-headline-sm text-on-surface mb-space-xs">{title}</h3>
        <p className="font-body-md text-body-md text-on-surface-variant">{description}</p>
      </div>
    </div>
  );
}

function toCsv(data: EvidenceOut) {
  const header = "symbol,date,today_change_pct,peer_change_pct,residual_pct,z_score,rvol";
  const rows = data.caught_extra.map((r) => [r.symbol, r.date, r.today_change_pct, r.peer_change_pct, r.residual_pct, r.z_score, r.rvol].join(","));
  return [header, ...rows].join("\n");
}

function downloadCsv(data: EvidenceOut) {
  const blob = new Blob([toCsv(data)], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `caught-extra-${data.days}d.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export default function EvidencePage() {
  const { token, ready } = useSession();
  const [days, setDays] = useState<(typeof WINDOWS)[number]>(90);
  const { data, isLoading, isError, error } = useEvidence(Boolean(token), days);
  const needsSession = ready && !token;
  const ratio = data && data.engine.alerts > 0 ? data.naive_pct_2.alerts / data.engine.alerts : null;
  const cutRate = data && data.naive_pct_2.alerts > 0 ? (1 - data.engine.alerts / data.naive_pct_2.alerts) * 100 : null;

  return (
    <div className="min-h-dvh flex flex-col">
      <AppHeader />
      <main className="w-full flex-1 max-w-7xl mx-auto px-margin-mobile md:px-margin-tablet lg:px-margin-desktop">
        <div className="flex flex-col w-full pb-space-3xl">
          <div className="w-full flex flex-col md:flex-row md:items-center justify-between gap-space-md py-space-lg mb-space-base">
            <div className="flex flex-col gap-space-2xs">
              <div className="flex items-center gap-space-sm">
                <span className="inline-flex items-center gap-space-2xs px-space-sm py-space-2xs rounded-full bg-primary/10 text-primary font-label-sm text-label-sm uppercase tracking-wider">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                  Noise-reduction evidence
                </span>
                <span className="font-label-sm text-label-sm text-secondary hidden sm:inline">Peer-residual engine, replayed on stored bars</span>
              </div>
              <p className="font-body-sm text-body-sm text-on-surface-variant flex items-center gap-space-xs">
                <Icon name="verified" size={15} className="text-primary" />
                <span>
                  {data
                    ? `Computed ${formatDay(data.computed_at.slice(0, 10))} ${formatClock(data.computed_at)} IST from stored end-of-day bars • No live network • ${data.symbols_count} watchlist symbols across ${data.days} sessions`
                    : "Replays three alert rules over the same end-of-day bars for your watchlist."}
                </span>
              </p>
            </div>
            <div className="flex items-center bg-surface-container-low p-space-2xs rounded-xl shadow-sm self-start md:self-auto" role="group" aria-label="Window">
              {WINDOWS.map((window) => (
                <button
                  key={window}
                  type="button"
                  onClick={() => setDays(window)}
                  aria-pressed={days === window}
                  className={`px-space-md py-space-xs rounded-lg font-label-md text-label-md transition-all flex items-center gap-space-2xs ${days === window ? "bg-surface-container-lowest text-primary font-bold shadow-sm" : "text-on-surface-variant hover:text-on-surface"}`}
                >
                  <span>{window} days</span>
                  {days === window && <span className="w-1.5 h-1.5 rounded-full bg-primary" />}
                </button>
              ))}
            </div>
          </div>

          {needsSession && (
            <div className="rounded-xl bg-surface-container-lowest shadow-sm px-space-xl py-space-2xl mb-space-2xl">
              <p className="font-body-lg text-body-lg text-on-surface">This replay runs against your watchlist, so it needs a session.</p>
              <Link href="/" className="mt-space-md inline-flex items-center gap-space-xs rounded-lg bg-primary-container px-space-lg py-space-sm font-label-lg text-label-lg font-bold text-on-primary-fixed">
                Start a session <Icon name="arrow_forward" size={16} />
              </Link>
            </div>
          )}

          {isLoading && (
            <div className="space-y-space-lg" aria-hidden>
              <div className="skeleton h-48" />
              <div className="skeleton h-64" />
            </div>
          )}

          {isError && <p role="alert" className="font-body-md text-body-md text-tertiary">The evidence run could not be loaded: {error.message}</p>}

          {data && (
            <>
              <div className="relative overflow-hidden rounded-xl bg-surface-container-lowest shadow-sm p-space-xl md:p-space-2xl mb-space-2xl">
                <div className="absolute -right-16 -top-16 w-96 h-96 rounded-full bg-gradient-to-br from-primary-container/10 via-primary-fixed/5 to-transparent blur-3xl pointer-events-none" />
                <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-space-xl">
                  <div className="max-w-3xl flex flex-col gap-space-sm">
                    <span className="self-start px-space-sm py-space-2xs rounded-full bg-secondary-container text-on-secondary-container font-label-sm text-label-sm uppercase">
                      Evaluation • {data.symbols_count} symbols • {data.days} days ({formatDay(data.from_date)} to {formatDay(data.to_date)})
                    </span>
                    <h1 className="font-headline-xl text-headline-xl text-on-surface tracking-tight">
                      {ratio !== null ? (
                        <>
                          A 2% rule would have interrupted you{" "}
                          <span className="text-primary underline decoration-primary-container decoration-4 underline-offset-8">{ratio.toFixed(1)}× more often</span>.
                        </>
                      ) : (
                        <>The engine fired nothing in this window; a 2% rule fired {data.naive_pct_2.alerts} times.</>
                      )}
                    </h1>
                    <p className="font-body-lg text-body-lg text-on-surface-variant pt-space-xs">
                      A fixed percentage alert pings you for every market-wide swing. This engine subtracts what the stock&rsquo;s behavioural peers explain, normalises by the stock&rsquo;s own volatility, and applies a 0.75% floor, so what is left is the stock&rsquo;s own move.
                    </p>
                  </div>
                  <div className="flex lg:flex-col gap-space-md shrink-0">
                    <div className="bg-surface-container-low rounded-xl p-space-md min-w-[170px]">
                      <span className="font-label-sm text-label-sm text-secondary uppercase block">Alert cut rate</span>
                      <span className="font-metric-display text-metric-display text-primary font-bold tracking-tight tabular">{cutRate !== null ? `−${cutRate.toFixed(1)}%` : "—"}</span>
                      <span className="font-body-sm text-body-sm text-on-surface-variant block mt-space-2xs">versus the 2% rule</span>
                    </div>
                    <div className="bg-surface-container-low rounded-xl p-space-md min-w-[170px]">
                      <span className="font-label-sm text-label-sm text-secondary uppercase block">Caught extra</span>
                      <span className="font-metric-display text-metric-display text-on-surface font-bold tracking-tight tabular">+{data.caught_extra.length}</span>
                      <span className="font-body-sm text-body-sm text-on-surface-variant block mt-space-2xs">sub-2% moves the rule missed</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-surface-container-lowest rounded-xl shadow-sm p-space-xl md:p-space-2xl mb-space-2xl">
                <div className="flex flex-col md:flex-row md:items-end justify-between gap-space-md mb-space-xl">
                  <div>
                    <span className="font-label-sm text-label-sm text-primary uppercase font-bold tracking-wider">Comparative replay</span>
                    <h2 className="font-headline-lg text-headline-lg text-on-surface mt-space-2xs">Three rules, same bars</h2>
                    <p className="font-body-md text-body-md text-on-surface-variant">Alerts fired across {(data.symbols_count * data.days).toLocaleString("en-IN")} symbol-sessions on your watchlist.</p>
                  </div>
                </div>
                <div className="flex flex-col gap-space-lg">
                  <Bar index={1} title="Naive ±2% rule" badge="100% baseline" alerts={data.naive_pct_2.alerts} days={data.days} max={data.naive_pct_2.alerts} tone="bg-secondary/40" description="Fires whenever the close moved 2% or more, including every day the whole market did the same thing." />
                  <Bar index={2} title="Raw z-score ≥ 2" badge={`${data.naive_pct_2.alerts ? Math.round((data.raw_z_2.alerts / data.naive_pct_2.alerts) * 100) : 0}% of baseline`} alerts={data.raw_z_2.alerts} days={data.days} max={data.naive_pct_2.alerts} tone="bg-secondary" description="Normalises for each stock's own 20-day volatility, but still cannot tell a stock move from a sector move." />
                  <Bar index={3} title="Peer-residual engine" badge={`${data.naive_pct_2.alerts ? Math.round((data.engine.alerts / data.naive_pct_2.alerts) * 100) : 0}% of baseline`} alerts={data.engine.alerts} days={data.days} max={data.naive_pct_2.alerts} tone="bg-primary-container" description="Only the residual after subtracting behavioural peers, at 2σ or more against the stock's own residual history, above a 0.75% floor." isHighlighted />
                </div>
              </div>

              <div className="mb-space-2xl">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-space-xs mb-space-lg">
                  <div>
                    <div className="flex items-center gap-space-xs">
                      <Icon name="filter_alt_off" size={20} className="text-primary" />
                      <span className="font-label-sm text-label-sm text-primary uppercase font-bold tracking-wider">What was suppressed, and why</span>
                    </div>
                    <h2 className="font-headline-lg text-headline-lg text-on-surface mt-space-2xs">{data.suppressed.total.toLocaleString("en-IN")} naive alerts suppressed</h2>
                  </div>
                  <span className="font-body-sm text-body-sm text-on-surface-variant">Every suppressed alert has exactly one reason.</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-space-lg">
                  <SuppressedCard index={1} count={data.suppressed.market_wide} total={data.suppressed.total} title="Market-wide move" description="The peer group moved 1% or more in the same direction. The stock did nothing its peers did not." />
                  <SuppressedCard index={2} count={data.suppressed.below_floor} total={data.suppressed.total} title="Below the 0.75% floor" description="After subtracting peers, less than 0.75% was left. Statistically loud on a low-volatility name, economically irrelevant." />
                  <SuppressedCard index={3} count={data.suppressed.within_noise} total={data.suppressed.total} title="Within its own noise" description="More than the floor was left, but under two standard deviations for a stock that moves this much every week." />
                </div>
              </div>

              <div className="bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden mb-space-2xl">
                <div className="p-space-xl md:p-space-2xl">
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-space-md">
                    <div>
                      <div className="flex items-center gap-space-xs">
                        <Icon name="radar" size={20} className="text-primary" />
                        <span className="font-label-sm text-label-sm text-primary uppercase font-bold tracking-wider">Bidirectional proof</span>
                      </div>
                      <h2 className="font-headline-lg text-headline-lg text-on-surface mt-space-2xs">Caught extra: moves the 2% rule never saw</h2>
                      <p className="font-body-md text-body-md text-on-surface-variant mt-space-xs max-w-2xl">
                        Each of these moved less than 2%, so a threshold rule stayed silent. Against a peer group going the other way, they were among the largest stock-specific moves in the window.
                      </p>
                    </div>
                    <div className="flex items-center gap-space-sm bg-surface-container-low px-space-md py-space-sm rounded-xl shrink-0">
                      <Icon name="troubleshoot" size={24} className="text-primary" />
                      <div>
                        <span className="font-label-sm text-label-sm text-secondary block">Removes noise and catches</span>
                        <span className="font-metric-tabular text-label-lg text-on-surface font-bold">+{data.caught_extra.length} sub-2% moves</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left font-metric-tabular text-metric-tabular">
                    <thead className="bg-surface-container-low text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider">
                      <tr>
                        <th className="py-space-md px-space-xl" scope="col">Symbol</th>
                        <th className="py-space-md px-space-md" scope="col">Date</th>
                        <th className="py-space-md px-space-md text-right" scope="col">Today %</th>
                        <th className="py-space-md px-space-md text-right" scope="col">Peers %</th>
                        <th className="py-space-md px-space-md text-right" scope="col">Stock-specific</th>
                        <th className="py-space-md px-space-md text-right" scope="col">z</th>
                        <th className="py-space-md px-space-md text-right" scope="col">RVOL</th>
                        <th className="py-space-md px-space-xl text-center" scope="col">Direction</th>
                      </tr>
                    </thead>
                    <tbody className="text-on-surface">
                      {data.caught_extra.length === 0 && (
                        <tr><td colSpan={8} className="py-space-xl px-space-xl text-secondary font-body-md">Nothing under 2% fired in this window.</td></tr>
                      )}
                      {data.caught_extra.map((row, index) => {
                        const isUp = row.residual_pct >= 0;
                        return (
                          <tr key={`${row.symbol}-${row.date}`} className={`hover:bg-surface-container-low/50 transition-colors ${index % 2 ? "bg-surface-container-low/20" : ""}`}>
                            <td className="py-space-md px-space-xl">
                              <div className="flex items-center gap-space-sm">
                                <div className={`w-8 h-8 rounded bg-surface-container flex items-center justify-center font-bold font-headline-sm text-body-sm ${isUp ? "text-primary" : "text-error"}`}>{initials(row.symbol)}</div>
                                <span className="font-headline-sm text-headline-sm text-on-surface">{stripSuffix(row.symbol)}</span>
                              </div>
                            </td>
                            <td className="py-space-md px-space-md text-secondary font-body-md">{formatDay(row.date)}</td>
                            <td className={`py-space-md px-space-md text-right font-bold tabular ${row.today_change_pct >= 0 ? "text-primary" : "text-error"}`}>{formatSignedPercent(row.today_change_pct)}</td>
                            <td className={`py-space-md px-space-md text-right font-medium tabular ${row.peer_change_pct >= 0 ? "text-primary" : "text-error"}`}>{formatSignedPercent(row.peer_change_pct)}</td>
                            <td className="py-space-md px-space-md text-right">
                              <span className={`inline-flex items-center px-space-sm py-space-2xs rounded font-bold tabular ${isUp ? "bg-primary-container/20 text-on-primary-container" : "bg-error-container text-on-error-container"}`}>{formatSignedPercent(row.residual_pct)}</span>
                            </td>
                            <td className={`py-space-md px-space-md text-right font-bold tabular ${isUp ? "text-primary" : "text-error"}`}>{row.z_score.toFixed(1)}σ</td>
                            <td className="py-space-md px-space-md text-right font-semibold tabular">{row.rvol.toFixed(1)}x</td>
                            <td className="py-space-md px-space-xl text-center">
                              <span className={`inline-flex items-center gap-space-2xs px-space-sm py-space-2xs rounded-full font-label-sm text-label-sm font-bold ${isUp ? "bg-primary/10 text-primary" : "bg-error-container text-on-error-container"}`}>
                                <span className={`w-1.5 h-1.5 rounded-full ${isUp ? "bg-primary" : "bg-error"}`} />
                                {isUp ? "BROKE AWAY UP" : "BROKE AWAY DOWN"}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="px-space-xl py-space-md bg-surface-container-low flex flex-col sm:flex-row items-center justify-between gap-space-sm text-on-surface-variant font-body-sm text-body-sm">
                  <div className="flex items-center gap-space-xs">
                    <Icon name="info" size={16} className="text-primary" />
                    <span>A naive 2% rule tagged 0 of these {data.caught_extra.length} moves. Top 20 by z-score are shown.</span>
                  </div>
                  <button type="button" onClick={() => downloadCsv(data)} className="font-label-sm text-label-sm text-primary font-bold hover:underline">Download as CSV →</button>
                </div>
              </div>

              <div className="bg-surface-container-lowest rounded-xl shadow-sm p-space-xl md:p-space-2xl mb-space-2xl">
                <div className="flex items-center gap-space-xs mb-space-xs">
                  <Icon name="policy" size={20} className="text-primary" />
                  <span className="font-label-sm text-label-sm text-primary uppercase font-bold tracking-wider">Named refusals</span>
                </div>
                <h2 className="font-headline-lg text-headline-lg text-on-surface mb-space-xs">Where AI is used, and where it is refused</h2>
                <p className="font-body-md text-body-md text-on-surface-variant max-w-3xl mb-space-xl">
                  Every number on this page comes from a formula a reader can check on paper. Models are allowed only where they cannot change what counts as meaningful.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-space-xl">
                  <div className="bg-surface-container-low/50 rounded-xl p-space-xl flex flex-col gap-space-md">
                    <div className="flex items-center gap-space-sm">
                      <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center"><Icon name="check" size={18} className="text-primary" /></div>
                      <h3 className="font-headline-sm text-headline-sm text-on-surface">Used</h3>
                    </div>
                    <ul className="flex flex-col gap-space-md font-body-md text-body-md text-on-surface-variant">
                      <li className="flex items-start gap-space-sm"><Icon name="grain" size={18} className="text-primary shrink-0 mt-0.5" /><div><strong className="text-on-surface">Unsupervised peer clustering:</strong> agglomerative clustering on a year of return correlations, recomputed weekly. No training data, no model artefacts.</div></li>
                      <li className="flex items-start gap-space-sm"><Icon name="chat" size={18} className="text-primary shrink-0 mt-0.5" /><div><strong className="text-on-surface">A model as narrator:</strong> the briefing is written from computed facts only and rejected if it contains a number, symbol, link, or advice word that was not in its input.</div></li>
                      <li className="flex items-start gap-space-sm"><Icon name="terminal" size={18} className="text-primary shrink-0 mt-0.5" /><div><strong className="text-on-surface">A model as compiler:</strong> plain English becomes a bounded JSON rule that you confirm before Python evaluates it. The model never sees a price.</div></li>
                    </ul>
                  </div>
                  <div className="bg-surface-container-low/50 rounded-xl p-space-xl flex flex-col gap-space-md">
                    <div className="flex items-center gap-space-sm">
                      <div className="w-7 h-7 rounded-full bg-error-container flex items-center justify-center"><Icon name="block" size={18} className="text-error" /></div>
                      <h3 className="font-headline-sm text-headline-sm text-on-surface">Refused</h3>
                    </div>
                    <ul className="flex flex-col gap-space-md font-body-md text-body-md text-on-surface-variant">
                      <li className="flex items-start gap-space-sm"><Icon name="query_stats" size={18} className="text-error shrink-0 mt-0.5" /><div><strong className="text-on-surface">No price prediction of any kind.</strong> An unbacktested forecast reads as naivety, not ambition.</div></li>
                      <li className="flex items-start gap-space-sm"><Icon name="psychology" size={18} className="text-error shrink-0 mt-0.5" /><div><strong className="text-on-surface">No anomaly-score ML.</strong> A score of 0.87 explains nothing; &ldquo;up 2.1% while peers were flat&rdquo; does.</div></li>
                      <li className="flex items-start gap-space-sm"><Icon name="shield" size={18} className="text-error shrink-0 mt-0.5" /><div><strong className="text-on-surface">No claim of predictive value.</strong> This surfaces what is statistically unusual, which is not the same as what is important. It has never been validated against outcomes.</div></li>
                    </ul>
                  </div>
                </div>
              </div>

              <div className="rounded-xl bg-surface-container-low p-space-xl flex flex-col lg:flex-row items-center justify-between gap-space-lg shadow-sm">
                <div className="flex items-center gap-space-md">
                  <div className="w-10 h-10 rounded-full bg-surface-container-lowest flex items-center justify-center shrink-0"><Icon name="database" size={24} className="text-primary" /></div>
                  <div>
                    <div className="flex items-center gap-space-xs">
                      <span className="font-headline-sm text-headline-sm text-on-surface">Replay cached for this watchlist</span>
                      <span className="w-2 h-2 rounded-full bg-primary-container" />
                    </div>
                    <p className="font-body-sm text-body-sm text-on-surface-variant">
                      Recomputed when your watchlist or the latest bar date changes, at most once an hour. Bars through {formatDay(data.to_date)}.
                    </p>
                  </div>
                </div>
                <Link href="/watchlist" className="px-space-lg py-space-sm rounded-lg bg-primary-container text-on-primary-container font-label-md text-label-md font-bold hover:brightness-95 transition-all flex items-center gap-space-xs shadow-sm">
                  <Icon name="arrow_back" size={16} />
                  <span>Back to the watchlist</span>
                </Link>
              </div>
            </>
          )}
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
