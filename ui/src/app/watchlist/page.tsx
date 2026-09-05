"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { isSessionGone } from "@/api/errors";
import { AlertsPanel } from "@/components/AlertsPanel";
import { AppHeader } from "@/components/AppHeader";
import { Banners } from "@/components/Banners";
import { DetailDrawer } from "@/components/DetailDrawer";
import { DigestHero } from "@/components/DigestHero";
import { QuietTable } from "@/components/QuietTable";
import { RuleComposer } from "@/components/RuleComposer";
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
  const { token, ready } = useSession();
  const digest = useDigest(Boolean(token));
  const briefing = useBriefing((digest.data?.total_count ?? 0) > 0);
  const seen = useSeen();
  const { add, remove } = useWatchlistItems();
  const [openSymbol, setOpenSymbol] = useState<string | null>(null);

  useEffect(() => {
    if (ready && !token) router.replace("/");
  }, [ready, token, router]);

  useEffect(() => {
    if (isSessionGone(digest.error)) router.replace("/?expired=1");
  }, [digest.error, router]);

  const items = useMemo(() => digest.data?.items ?? [], [digest.data]);
  const changed = items.filter((item) => item.is_changed);
  const quiet = items.filter((item) => !item.is_changed);
  const openItem = items.find((item) => item.symbol === openSymbol) ?? null;

  if (!ready || !token) {
    return (
      <main className="flex min-h-dvh items-center justify-center px-6">
        <p className="font-body-md text-body-md text-secondary">Checking your session…</p>
      </main>
    );
  }

  return (
    <div className="min-h-dvh flex flex-col">
      <AppHeader digest={digest.data} />
      <main className="w-full flex-1 max-w-7xl mx-auto px-margin-mobile md:px-margin-tablet lg:px-margin-desktop pt-space-xl">
        <div className="flex flex-col w-full pb-space-3xl space-y-space-xl">
          <Banners digest={digest.data} error={digest.error} onRetry={() => digest.refetch()} briefingError={briefing.error} />

          {digest.isPending && (
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
                error={add.error}
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
                        onSeen={() => seen.mutate([item.symbol])}
                        isSeenPending={seen.isPending}
                      />
                    ))}
                  </div>
                </section>
              )}

              {digest.data.total_count === 0 && (
                <section className="rounded-xl border border-dashed border-outline-variant bg-surface-container-lowest px-space-xl py-space-3xl text-center">
                  <h2 className="font-headline-sm text-headline-sm text-on-surface">Nothing to watch yet</h2>
                  <p className="mx-auto mt-space-xs max-w-[46ch] font-body-sm text-body-sm text-secondary">
                    Add a few NSE symbols above. The digest needs at least one stock before it can tell you what its peer group did and what it did on its own.
                  </p>
                </section>
              )}

              <QuietTable items={quiet} onOpen={setOpenSymbol} onRemove={(symbol) => remove.mutate(symbol)} />

              <RuleComposer enabled={Boolean(token)} />

              <AlertsPanel enabled={Boolean(token)} />
            </>
          )}
        </div>
      </main>
      <SiteFooter />

      {openItem && (
        <DetailDrawer
          item={openItem}
          onClose={() => setOpenSymbol(null)}
          onSeen={() => seen.mutate([openItem.symbol], { onSuccess: () => setOpenSymbol(null) })}
          onRemove={() => remove.mutate(openItem.symbol, { onSuccess: () => setOpenSymbol(null) })}
          isSeenPending={seen.isPending}
        />
      )}
    </div>
  );
}
