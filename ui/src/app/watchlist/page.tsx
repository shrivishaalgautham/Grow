"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { isRateLimited, isSessionGone } from "@/api/errors";
import type { DigestOut } from "@/api/types";
import { AppHeader } from "@/components/AppHeader";
import { DetailDrawer } from "@/components/DetailDrawer";
import { DigestHero } from "@/components/DigestHero";
import { QuietTable } from "@/components/QuietTable";
import { ResumeLink } from "@/components/ResumeLink";
import { RuleComposer } from "@/components/RuleComposer";
import { StateBanner } from "@/components/StateBanner";
import { StockCard } from "@/components/StockCard";
import { SymbolSearch } from "@/components/SymbolSearch";
import { useBriefing } from "@/hooks/useBriefing";
import { useDigest } from "@/hooks/useDigest";
import { useHealth } from "@/hooks/useHealth";
import { useSeen } from "@/hooks/useSeen";
import { useSession } from "@/hooks/useSession";
import { useWatchlistItems } from "@/hooks/useWatchlistItems";
import { formatDay, formatRetryAfter } from "@/lib/format";

const RESUME_SHOWN_KEY = "swl.resume_shown";
const CATALYST_PREFETCH_COUNT = 3;

function CardSkeleton() {
  return (
    <div className="h-56 rounded-xl border border-line bg-surface p-5">
      <div className="skeleton h-4 w-28 rounded" />
      <div className="skeleton mt-3 h-3 w-48 rounded" />
      <div className="skeleton mt-6 h-16 w-full rounded" />
      <div className="skeleton mt-4 h-3 w-2/3 rounded" />
    </div>
  );
}

export default function WatchlistPage() {
  const router = useRouter();
  const { token, ready, end } = useSession();

  const digest = useDigest(Boolean(token));
  const briefing = useBriefing((digest.data?.total_count ?? 0) > 0);
  const seen = useSeen();
  const { add, remove } = useWatchlistItems();

  const [openSymbol, setOpenSymbol] = useState<string | null>(null);
  const [isResumeOpen, setIsResumeOpen] = useState(false);
  const [isHintDismissed, setIsHintDismissed] = useState(false);

  useEffect(() => {
    if (ready && !token) router.replace("/");
  }, [ready, token, router]);

  const showResumeHint =
    ready &&
    Boolean(token) &&
    !isHintDismissed &&
    window.localStorage.getItem(RESUME_SHOWN_KEY) === null;

  function dismissHint() {
    window.localStorage.setItem(RESUME_SHOWN_KEY, "1");
    setIsHintDismissed(true);
  }

  const health = useHealth(digest.data?.providers_degraded === true);
  const failingProviders =
    health.data?.providers
      .filter((provider) => provider.circuit_state !== "closed")
      .map((provider) => provider.provider) ?? [];

  const items = useMemo(() => digest.data?.items ?? [], [digest.data]);
  const changed = items.filter((item) => item.is_changed);
  const quiet = items.filter((item) => !item.is_changed);
  const openItem = items.find((item) => item.symbol === openSymbol) ?? null;

  if (!ready || !token) {
    return (
      <main className="flex min-h-dvh items-center justify-center px-6">
        <p className="text-sm text-muted">Checking your session…</p>
      </main>
    );
  }

  return (
    <div className="min-h-dvh">
      <AppHeader
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsResumeOpen(true)}
              className="shrink-0 rounded-md border border-line px-2.5 py-1.5 text-[13px] whitespace-nowrap text-muted transition-colors hover:border-line-strong hover:text-ink"
            >
              <span className="hidden sm:inline">Open on phone</span>
              <span className="sm:hidden">Phone</span>
            </button>
            <button
              type="button"
              onClick={() => end.mutate()}
              disabled={end.isPending}
              title="Deletes this session and its watchlist on the server"
              className="shrink-0 rounded-md px-2 py-1.5 text-[13px] whitespace-nowrap text-faint transition-colors hover:text-down disabled:opacity-50"
            >
              End session
            </button>
          </div>
        }
      />

      <main className="mx-auto max-w-5xl space-y-5 px-4 py-6 sm:px-6 sm:py-8">
        <Banners
          digest={digest.data}
          error={digest.error}
          onRetry={() => digest.refetch()}
          failingProviders={failingProviders}
          isBriefingRateLimited={isRateLimited(briefing.error)}
          briefingRetryAfter={
            isRateLimited(briefing.error)
              ? (briefing.error.retryAfterSeconds ?? 60)
              : null
          }
        />

        {digest.isPending && (
          <>
            <div className="h-44 rounded-xl border border-line bg-surface p-6">
              <div className="skeleton h-6 w-2/3 rounded" />
              <div className="skeleton mt-4 h-3.5 w-full rounded" />
              <div className="skeleton mt-2 h-3.5 w-5/6 rounded" />
            </div>
            <CardSkeleton />
            <CardSkeleton />
          </>
        )}

        {showResumeHint && (
          <StateBanner
            tone="info"
            title="Carry this watchlist to your phone"
            action={
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    dismissHint();
                    setIsResumeOpen(true);
                  }}
                  className="rounded-md border border-notable/40 px-3 py-1.5 text-xs font-medium text-notable"
                >
                  Show QR
                </button>
                <button
                  type="button"
                  onClick={dismissHint}
                  className="rounded-md px-2 py-1.5 text-xs text-faint hover:text-ink"
                >
                  Dismiss
                </button>
              </div>
            }
          >
            A one-time link resumes this session on another device. It stays in
            the menu.
          </StateBanner>
        )}

        {digest.data && (
          <>
            <DigestHero
              digest={digest.data}
              briefing={briefing.data}
              isBriefingLoading={briefing.isLoading}
              onMarkAll={() => seen.mutate("all")}
              isMarkAllPending={seen.isPending}
            />

            <SymbolSearch
              owned={items.map((item) => item.symbol)}
              onAdd={(symbol) => add.mutate(symbol)}
              isAdding={add.isPending}
            />

            {add.isError && (
              <p role="alert" className="text-[13px] text-down">
                {add.error.message}
              </p>
            )}

            {digest.data.total_count === 0 && <EmptyWatchlist />}

            {changed.length > 0 && (
              <section aria-label="Stocks that changed" className="space-y-3">
                <h2 className="text-[11px] font-medium tracking-wide text-faint uppercase">
                  Changed · ranked by how much is stock-specific
                </h2>
                {changed.map((item, rank) => (
                  <StockCard
                    key={item.symbol}
                    item={item}
                    prefetchCatalysts={rank < CATALYST_PREFETCH_COUNT}
                    onOpen={() => setOpenSymbol(item.symbol)}
                    onSeen={() => seen.mutate([item.symbol])}
                    isSeenPending={seen.isPending}
                  />
                ))}
              </section>
            )}

            <QuietTable
              items={quiet}
              onOpen={setOpenSymbol}
              onRemove={(symbol) => remove.mutate(symbol)}
            />

            <RuleComposer enabled={Boolean(token)} />
          </>
        )}
      </main>

      {openItem && (
        <DetailDrawer item={openItem} onClose={() => setOpenSymbol(null)} />
      )}

      {isResumeOpen && token && (
        <ResumeLink token={token} onClose={() => setIsResumeOpen(false)} />
      )}
    </div>
  );
}

function EmptyWatchlist() {
  return (
    <section className="rounded-xl border border-dashed border-line-strong bg-surface px-6 py-12 text-center">
      <h2 className="text-base font-semibold text-ink">
        Nothing to watch yet
      </h2>
      <p className="mx-auto mt-2 max-w-[46ch] text-[13px] leading-relaxed text-muted">
        Add a few NSE symbols above. The digest needs at least one stock before
        it can tell you what its peer group did and what it did on its own.
      </p>
    </section>
  );
}

function Banners({
  digest,
  error,
  onRetry,
  failingProviders,
  isBriefingRateLimited,
  briefingRetryAfter,
}: {
  digest: DigestOut | undefined;
  error: Error | null;
  onRetry: () => void;
  failingProviders: string[];
  isBriefingRateLimited: boolean;
  briefingRetryAfter: number | null;
}) {
  return (
    <>
      {isSessionGone(error) && (
        <StateBanner tone="warn" title="Your session expired">
          Sending you back to the start page to begin a new one.
        </StateBanner>
      )}

      {isRateLimited(error) && (
        <StateBanner tone="warn" title="Too many requests">
          {`The API is rate limiting this session. Retry in ${formatRetryAfter(error.retryAfterSeconds ?? 60)}.`}
        </StateBanner>
      )}

      {error && !isSessionGone(error) && !isRateLimited(error) && (
        <StateBanner
          tone="warn"
          title="Could not load your watchlist"
          action={
            <button
              type="button"
              onClick={onRetry}
              className="rounded-md border border-delayed/40 px-3 py-1.5 text-xs font-medium text-delayed"
            >
              Try again
            </button>
          }
        >
          The API did not respond. Your watchlist and seen-state are untouched.
        </StateBanner>
      )}

      {isBriefingRateLimited && briefingRetryAfter !== null && (
        <StateBanner tone="warn" title="Briefing is rate limited">
          {`The written summary is capped to protect the model budget. The digest below is unaffected. Retry in ${formatRetryAfter(briefingRetryAfter)}.`}
        </StateBanner>
      )}

      {digest?.replay_date && (
        <StateBanner tone="info" title="Replay mode">
          {`The clock is pinned to ${formatDay(digest.replay_date)} for rehearsal. These are real bars from that session, not live prices.`}
        </StateBanner>
      )}

      {digest?.providers_degraded && (
        <StateBanner tone="warn" title="Price providers are degraded">
          {failingProviders.length > 0
            ? `${failingProviders.join(" and ")} stopped answering, so every card falls back to the last known good quote. Signals are still computed from real bars; only the prices are behind.`
            : "Every card falls back to the last known good quote. The signals are still computed from real bars; only the prices are behind."}
        </StateBanner>
      )}

      {digest?.market_status === "closed" && !digest.providers_degraded && (
        <StateBanner title="Market is closed">
          Prices are the last close. The digest still covers everything that
          happened while you were away.
        </StateBanner>
      )}

      {digest?.market_status === "pre_open" && (
        <StateBanner title="Pre-open session">
          Quotes are indicative until the market opens at 09:15 IST.
        </StateBanner>
      )}

      {digest && digest.last_reviewed_at === null && digest.total_count > 0 && (
        <StateBanner tone="info" title="First look">
          There is no last-review point yet, so nothing is measured against
          &ldquo;since you looked&rdquo;. Mark this reviewed and the next visit
          will be a proper diff.
        </StateBanner>
      )}

      {digest && digest.total_count > 0 && digest.changed_count === 0 && (
        <StateBanner title="A quiet stretch">
          Nothing cleared the bar. That is the engine working, not a failure —
          a naive 2% rule would have found something to say here.
        </StateBanner>
      )}
    </>
  );
}
