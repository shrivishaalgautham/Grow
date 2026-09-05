"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { isSessionGone } from "@/api/errors";
import { demoBriefing, demoDigest } from "@/api/fixture";
import { AlertsPanel } from "@/components/AlertsPanel";
import { AppHeader } from "@/components/AppHeader";
import { Banners } from "@/components/Banners";
import { DetailDrawer } from "@/components/DetailDrawer";
import { DigestHero } from "@/components/DigestHero";
import { Icon } from "@/components/Icon";
import { QuietTable } from "@/components/QuietTable";
import { RuleComposer } from "@/components/RuleComposer";
import { SignInPrompt, useSignInPrompt } from "@/components/SignInPrompt";
import { SiteFooter } from "@/components/SiteFooter";
import { StockCard } from "@/components/StockCard";
import { SymbolSearch } from "@/components/SymbolSearch";
import { useBriefing } from "@/hooks/useBriefing";
import { useDigest } from "@/hooks/useDigest";
import { useSeen } from "@/hooks/useSeen";
import { useSession } from "@/hooks/useSession";
import { useWatchlistItems } from "@/hooks/useWatchlistItems";

const CATALYST_PREFETCH_COUNT = 3;

function CardSkeleton() {
  return (
    <div className="bg-surface-container-lowest rounded-xl p-space-xl shadow-sm space-y-space-md" aria-hidden>
      <div className="skeleton h-6 w-40" />
      <div className="skeleton h-4 w-64" />
      <div className="skeleton h-24 w-full" />
      <div className="skeleton h-4 w-2/3" />
    </div>
  );
}

export default function WatchlistPage() {
  const router = useRouter();
  const { token, ready, signInWithGoogle } = useSession();
  const isDemo = ready && !token;
  const digest = useDigest(Boolean(token));
  const briefing = useBriefing(!isDemo && (digest.data?.total_count ?? 0) > 0);
  const seen = useSeen();
  const { add, remove } = useWatchlistItems();
  const { blockedAction, requireSignIn, dismiss } = useSignInPrompt();
  const [openSymbol, setOpenSymbol] = useState<string | null>(null);

  const demo = useMemo(
    () => (isDemo ? { digest: demoDigest(), briefing: demoBriefing() } : null),
    [isDemo],
  );

  useEffect(() => {
    if (isSessionGone(digest.error)) router.replace("/?expired=1");
  }, [digest.error, router]);

  const data = demo?.digest ?? digest.data;
  const items = useMemo(() => data?.items ?? [], [data]);
  const changed = items.filter((item) => item.is_changed);
  const quiet = items.filter((item) => !item.is_changed);
  const openItem = items.find((item) => item.symbol === openSymbol) ?? null;

  if (!ready || isSessionGone(digest.error)) {
    return (
      <main className="flex min-h-dvh items-center justify-center px-6">
        <p className="font-body-md text-body-md text-secondary">Checking your session…</p>
      </main>
    );
  }

  return (
    <div className="min-h-dvh flex flex-col">
      <AppHeader digest={data} />
      {isDemo && (
        <div className="w-full bg-secondary-container text-on-secondary-fixed">
          <div className="max-w-7xl mx-auto px-margin-mobile md:px-margin-tablet lg:px-margin-desktop py-space-sm flex flex-col sm:flex-row sm:items-center justify-between gap-space-sm">
            <div className="flex items-start gap-space-sm min-w-0">
              <Icon name="visibility" size={20} className="text-primary shrink-0 mt-0.5" />
              <p className="font-body-sm text-body-sm">
                <span className="font-bold">Live demo, sample data.</span> A fixed 12-stock NSE
                watchlist replayed from stored bars, shared by everyone who opens this link.
                Reading is free; changing anything needs a watchlist of your own.
              </p>
            </div>
            <div className="flex items-center gap-space-sm shrink-0">
              <button
                type="button"
                onClick={signInWithGoogle}
                className="flex items-center gap-space-xs px-space-md py-space-xs bg-primary-container text-on-primary-fixed rounded-lg font-label-md text-label-md font-bold shadow-sm hover:opacity-95 transition-opacity"
              >
                <Icon name="verified" size={18} />
                <span>Sign in to build your own</span>
              </button>
              <Link
                href="/#start"
                className="px-space-md py-space-xs bg-surface-container-lowest text-on-surface rounded-lg font-label-md text-label-md hover:bg-surface-container-low transition-colors"
              >
                Or start without an account
              </Link>
            </div>
          </div>
        </div>
      )}
      <main className="w-full flex-1 max-w-7xl mx-auto px-margin-mobile md:px-margin-tablet lg:px-margin-desktop pt-space-xl">
        <div className="flex flex-col w-full pb-space-3xl space-y-space-xl">
          <Banners digest={data} error={isDemo ? null : digest.error} onRetry={() => digest.refetch()} briefingError={isDemo ? null : briefing.error} />

          {digest.isPending && !isDemo && (
            <>
              <div className="bg-surface-container-lowest rounded-xl p-space-2xl shadow-sm space-y-space-md" aria-hidden>
                <div className="skeleton h-8 w-2/3" />
                <div className="skeleton h-4 w-full" />
                <div className="skeleton h-4 w-5/6" />
              </div>
              <CardSkeleton />
              <CardSkeleton />
            </>
          )}

          {data && (
            <>
              <DigestHero
                digest={data}
                briefing={demo?.briefing ?? briefing.data}
                isBriefingLoading={!isDemo && briefing.isLoading}
                onMarkAll={isDemo ? requireSignIn("clear your own alerts") : () => seen.mutate("all")}
                isMarkAllPending={seen.isPending}
              />

              <SymbolSearch
                owned={items.map((item) => item.symbol)}
                onAdd={isDemo ? requireSignIn("add a symbol") : (symbol) => add.mutate(symbol)}
                isAdding={!isDemo && add.isPending}
                error={isDemo ? null : add.error}
              />

              {changed.length > 0 && (
                <section className="space-y-space-md">
                  <div className="flex items-center justify-between gap-space-md">
                    <div className="flex items-center gap-space-sm">
                      <h2 className="font-headline-md text-headline-md text-on-surface">Changed since you looked</h2>
                      <span className="px-space-sm py-space-2xs bg-primary/10 text-primary font-label-sm text-label-sm rounded-full font-bold">
                        {changed.length} with signals
                      </span>
                    </div>
                    <div className="font-label-sm text-label-sm text-secondary hidden sm:block">Ranked by how much is stock-specific</div>
                  </div>
                  <div className="grid grid-cols-1 gap-space-lg">
                    {changed.map((item, rank) => (
                      <StockCard
                        key={item.symbol}
                        item={item}
                        prefetchCatalysts={rank < CATALYST_PREFETCH_COUNT}
                        onOpen={() => setOpenSymbol(item.symbol)}
                        onSeen={isDemo ? requireSignIn("mark this reviewed") : () => seen.mutate([item.symbol])}
                        isSeenPending={seen.isPending}
                      />
                    ))}
                  </div>
                </section>
              )}

              {data.total_count === 0 && (
                <section className="rounded-xl border border-dashed border-outline-variant bg-surface-container-lowest px-space-xl py-space-3xl text-center">
                  <h2 className="font-headline-sm text-headline-sm text-on-surface">Nothing to watch yet</h2>
                  <p className="mx-auto mt-space-xs max-w-[46ch] font-body-sm text-body-sm text-secondary">
                    Add a few NSE symbols above. The digest needs at least one stock before it can tell you what its peer group did and what it did on its own.
                  </p>
                </section>
              )}

              <QuietTable
                items={quiet}
                onOpen={setOpenSymbol}
                onRemove={isDemo ? requireSignIn("remove a symbol") : (symbol) => remove.mutate(symbol)}
              />

              <RuleComposer
                enabled={Boolean(token)}
                onRequireSignIn={isDemo ? requireSignIn("save this rule") : undefined}
              />

              <AlertsPanel
                enabled={Boolean(token)}
                onRequireSignIn={isDemo ? requireSignIn("get these by email") : undefined}
              />
            </>
          )}
        </div>
      </main>
      <SiteFooter />

      {openItem && (
        <DetailDrawer
          item={openItem}
          onClose={() => setOpenSymbol(null)}
          onSeen={isDemo ? requireSignIn("mark this reviewed") : () => seen.mutate([openItem.symbol], { onSuccess: () => setOpenSymbol(null) })}
          onRemove={isDemo ? requireSignIn("remove a symbol") : () => remove.mutate(openItem.symbol, { onSuccess: () => setOpenSymbol(null) })}
          isSeenPending={seen.isPending}
        />
      )}

      {blockedAction && <SignInPrompt action={blockedAction} onDismiss={dismiss} />}
    </div>
  );
}
