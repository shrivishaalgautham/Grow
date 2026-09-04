"use client";

import Link from "next/link";
import type { EvidenceOut } from "@/api/types";
import { AppHeader } from "@/components/AppHeader";
import { useEvidence } from "@/hooks/useEvidence";
import { useSession } from "@/hooks/useSession";
import { formatDay, formatSignedPercent, stripSuffix } from "@/lib/format";

function Bar({
  label,
  detail,
  alerts,
  max,
  tone,
}: {
  label: string;
  detail: string;
  alerts: number;
  max: number;
  tone: string;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-4">
        <p className="text-sm font-medium text-ink">{label}</p>
        <p className="numeric text-sm text-ink">
          {alerts.toLocaleString("en-IN")}
        </p>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-line">
        <div
          className={`h-full rounded-full ${tone}`}
          style={{ width: `${(alerts / max) * 100}%` }}
        />
      </div>
      <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{detail}</p>
    </div>
  );
}

function Suppression({ data }: { data: EvidenceOut }) {
  const rows = [
    [
      "Market-wide",
      data.suppressed.market_wide,
      "The whole market moved. The stock did nothing its peers did not.",
    ],
    [
      "Below the floor",
      data.suppressed.below_floor,
      "Residual under the 0.75% floor — statistically loud, economically irrelevant.",
    ],
    [
      "Volume unconfirmed",
      data.suppressed.unconfirmed_volume,
      "A price move on a thin book, with no volume behind it.",
    ],
  ] as const;

  return (
    <div className="space-y-3">
      {rows.map(([label, count, why]) => (
        <div
          key={label}
          className="flex items-start justify-between gap-4 rounded-lg border border-line bg-raised px-4 py-3"
        >
          <div className="min-w-0">
            <p className="text-[13px] font-medium text-ink">{label}</p>
            <p className="mt-0.5 text-[13px] leading-relaxed text-muted">
              {why}
            </p>
          </div>
          <p className="numeric shrink-0 text-sm text-muted">
            {count.toLocaleString("en-IN")}
          </p>
        </div>
      ))}
    </div>
  );
}

export default function EvidencePage() {
  const { token, ready } = useSession();
  const { data, isLoading, isError, error } = useEvidence(Boolean(token));
  const needsSession = ready && !token;

  return (
    <div className="min-h-dvh">
      <AppHeader />

      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-12">
        <h1 className="text-2xl leading-tight font-semibold text-balance text-ink sm:text-3xl">
          {data
            ? `A 2% rule would have interrupted you ${(data.naive_pct_2.alerts / data.engine.alerts).toFixed(1)}× more often.`
            : "How much noise the engine removes."}
        </h1>
        <p className="mt-3 max-w-[62ch] text-[15px] leading-relaxed text-muted">
          Replayed over real end-of-day bars, this compares three rules on the
          same data: alert on any 2% move, alert on a raw z-score of 2, and the
          peer-adjusted engine this app actually runs.
        </p>

        {needsSession && (
          <div className="mt-8 rounded-xl border border-line bg-surface px-6 py-8">
            <p className="text-[15px] text-ink">
              This replay runs against the seeded universe, so it needs a
              session.
            </p>
            <Link
              href="/"
              className="mt-4 inline-block rounded-lg bg-ink px-4 py-2.5 text-sm font-semibold text-canvas"
            >
              Start a session
            </Link>
          </div>
        )}

        {isLoading && (
          <div className="mt-10 space-y-4" aria-hidden>
            <div className="skeleton h-20 rounded-lg" />
            <div className="skeleton h-20 rounded-lg" />
            <div className="skeleton h-20 rounded-lg" />
          </div>
        )}

        {isError && (
          <p role="alert" className="mt-10 text-sm text-down">
            The evidence run could not be loaded: {error.message}
          </p>
        )}

        {data && (
          <>
            <p className="numeric mt-6 text-[11px] tracking-wide text-faint uppercase">
              {data.symbols_count} symbols · {data.days} days ·{" "}
              {formatDay(data.from_date)} to {formatDay(data.to_date)}
            </p>

            <section className="mt-8 space-y-6 rounded-xl border border-line bg-surface p-5 sm:p-6">
              <Bar
                label="Naive: any move over 2%"
                detail="Fires on every market-wide selloff, every index rally, every thin-book twitch."
                alerts={data.naive_pct_2.alerts}
                max={data.naive_pct_2.alerts}
                tone="bg-down"
              />
              <Bar
                label="Raw z-score ≥ 2"
                detail="Normalises for each stock's own volatility, but still cannot tell a stock move from a market move."
                alerts={data.raw_z_2.alerts}
                max={data.naive_pct_2.alerts}
                tone="bg-delayed"
              />
              <Bar
                label="This engine"
                detail="Peer-adjusted residual, volatility-normalised, volume-confirmed, with a 0.75% economic floor."
                alerts={data.engine.alerts}
                max={data.naive_pct_2.alerts}
                tone="bg-up"
              />
            </section>

            <section className="mt-10">
              <h2 className="text-sm font-semibold text-ink">
                What was suppressed, and why
              </h2>
              <p className="mt-1.5 text-[13px] text-muted">
                {data.suppressed.total.toLocaleString("en-IN")} of the naive
                rule&rsquo;s alerts were dropped. Every one has a reason.
              </p>
              <div className="mt-4">
                <Suppression data={data} />
              </div>
            </section>

            <section className="mt-10">
              <h2 className="text-sm font-semibold text-ink">
                Caught extra — moves the 2% rule never saw
              </h2>
              <p className="mt-1.5 max-w-[62ch] text-[13px] leading-relaxed text-muted">
                Each of these moved less than 2%, so a threshold rule stayed
                silent. Against a peer group going the other way, they were
                among the largest stock-specific moves in the window.
              </p>

              <div className="mt-4 overflow-x-auto rounded-xl border border-line bg-surface">
                <table className="w-full min-w-[34rem] border-collapse text-sm">
                  <thead>
                    <tr className="text-[11px] tracking-wide text-faint uppercase">
                      <th scope="col" className="px-4 py-2.5 text-left font-medium">
                        Symbol
                      </th>
                      <th scope="col" className="px-4 py-2.5 text-left font-medium">
                        Date
                      </th>
                      <th scope="col" className="px-4 py-2.5 text-right font-medium">
                        Today
                      </th>
                      <th scope="col" className="px-4 py-2.5 text-right font-medium">
                        Peers
                      </th>
                      <th scope="col" className="px-4 py-2.5 text-right font-medium">
                        Stock-specific
                      </th>
                      <th scope="col" className="px-4 py-2.5 text-right font-medium">
                        z
                      </th>
                      <th scope="col" className="px-4 py-2.5 text-right font-medium">
                        rvol
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.caught_extra.map((row) => (
                      <tr
                        key={`${row.symbol}-${row.date}`}
                        className="border-t border-line/70"
                      >
                        <th
                          scope="row"
                          className="numeric px-4 py-2.5 text-left font-normal text-ink"
                        >
                          {stripSuffix(row.symbol)}
                        </th>
                        <td className="numeric px-4 py-2.5 text-left text-faint">
                          {formatDay(row.date)}
                        </td>
                        <td className="numeric px-4 py-2.5 text-right text-muted">
                          {formatSignedPercent(row.today_change_pct)}
                        </td>
                        <td className="numeric px-4 py-2.5 text-right text-muted">
                          {formatSignedPercent(row.peer_change_pct)}
                        </td>
                        <td
                          className={`numeric px-4 py-2.5 text-right ${row.residual_pct >= 0 ? "text-up" : "text-down"}`}
                        >
                          {formatSignedPercent(row.residual_pct)}
                        </td>
                        <td className="numeric px-4 py-2.5 text-right text-muted">
                          {row.z_score.toFixed(2)}
                        </td>
                        <td className="numeric px-4 py-2.5 text-right text-muted">
                          {row.rvol.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <p className="mt-8 text-xs text-faint">
              Computed {formatDay(data.computed_at.slice(0, 10))} from stored
              end-of-day bars. No live network call is involved.
            </p>
          </>
        )}
      </main>
    </div>
  );
}
