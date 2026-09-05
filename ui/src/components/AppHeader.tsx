"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { DigestOut } from "@/api/types";
import { useHealth } from "@/hooks/useHealth";
import { useMe } from "@/hooks/useMe";
import { useSession } from "@/hooks/useSession";
import { formatClock } from "@/lib/format";
import { Icon } from "./Icon";
import { ResumeModal } from "./ResumeModal";

function ProviderStrip({ digest }: { digest?: DigestOut }) {
  const [isDismissed, setIsDismissed] = useState(false);
  const health = useHealth(true);
  if (isDismissed || !health.data) return null;

  const isDegraded =
    health.data.providers.some((p) => p.circuit_state !== "closed") || digest?.providers_degraded === true;
  if (!isDegraded) return null;

  return (
    <div className="w-full px-gutter-desktop py-space-xs bg-tertiary-fixed/60 text-on-tertiary-fixed">
      <div className="max-w-7xl mx-auto w-full flex items-center justify-between gap-space-md">
        <div className="flex items-center gap-space-sm min-w-0">
          <Icon name="warning" size={16} className="text-tertiary shrink-0" />
          <span className="font-body-sm text-body-sm truncate">
            Some prices may be a few minutes old while we reconnect to a data source.
          </span>
        </div>
        <button
          type="button"
          onClick={() => setIsDismissed(true)}
          aria-label="Dismiss price delay notice"
          className="font-label-sm text-label-sm text-secondary hover:text-on-surface shrink-0"
        >
          <Icon name="close" size={14} />
        </button>
      </div>
    </div>
  );
}

export function AppHeader({ digest }: { digest?: DigestOut }) {
  const router = useRouter();
  const { token, ready, end, signInWithGoogle } = useSession();
  const me = useMe(Boolean(token));
  const [isResumeOpen, setIsResumeOpen] = useState(false);
  const isDemo = ready && !token;

  function endSession() {
    if (!window.confirm("End this session on this device? You will need to sign back in, or reopen your resume link, to continue.")) return;
    end.mutate(undefined, { onSettled: () => router.replace("/") });
  }

  const marketLabel =
    digest?.market_status === "open" ? "Market Open" : digest?.market_status === "pre_open" ? "Pre-open" : "Market Closed";

  return (
    <>
      <header className="sticky top-0 z-40 bg-surface-container-lowest/90 backdrop-blur-md shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
        <ProviderStrip digest={digest} />
        <div className="h-16 max-w-7xl mx-auto px-margin-mobile md:px-margin-tablet lg:px-margin-desktop flex items-center justify-between gap-space-md">
          <Link href="/watchlist" className="flex items-center gap-space-sm">
            <span className="w-8 h-8 rounded-lg bg-primary-container flex items-center justify-center text-on-primary-fixed">
              <Icon name="candlestick_chart" size={20} />
            </span>
            <span className="font-headline-sm text-headline-sm text-on-surface hidden sm:inline">
              Smart Market Watchlist
            </span>
          </Link>
          <div className="flex items-center gap-space-md">
            {digest && (
              <div className="hidden lg:flex items-center gap-space-xs bg-surface-container-low px-space-md py-space-xs rounded-full">
                <span
                  className={`w-2 h-2 rounded-full ${digest.market_status === "open" ? "bg-primary-container animate-pulse" : "bg-secondary"}`}
                />
                <span className="font-label-sm text-label-sm text-on-surface font-bold">{marketLabel}</span>
                <span className="font-body-sm text-body-sm text-on-surface-variant">{formatClock(digest.now)} IST</span>
              </div>
            )}
            <div className="flex items-center gap-space-xs bg-surface-container-low px-space-sm py-space-2xs rounded-full">
              <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
                <Icon name={isDemo ? "visibility" : "person"} size={18} className="text-on-primary" />
              </div>
              <span className="font-label-sm text-label-sm text-on-surface pr-space-xs hidden sm:inline">
                {isDemo ? "Viewing demo" : (me.data?.email ?? me.data?.display_name ?? "…")}
              </span>
            </div>
            {(isDemo || (me.data && !me.data.email)) && (
              <button
                type="button"
                onClick={signInWithGoogle}
                className="hidden sm:flex items-center gap-space-xs bg-primary-container px-space-md py-space-xs rounded-lg shadow-sm hover:opacity-95 transition-opacity font-label-md text-label-md text-on-primary-fixed"
              >
                <Icon name="verified" size={18} />
                <span>Sign in with Google</span>
              </button>
            )}
            {!isDemo && (
              <>
                <button
                  type="button"
                  aria-label="Open on phone"
                  onClick={() => setIsResumeOpen(true)}
                  className="flex min-h-10 items-center gap-space-xs bg-surface-container-lowest px-space-md py-space-xs rounded-lg shadow-[0_1px_3px_rgba(15,23,42,0.04)] hover:bg-surface-container-low transition-colors font-label-md text-label-md text-on-surface"
                >
                  <Icon name="qr_code_2" size={18} className="text-primary" />
                  <span className="hidden sm:inline">Open on phone</span>
                </button>
                <button
                  type="button"
                  aria-label="End session"
                  onClick={endSession}
                  disabled={end.isPending}
                  className="flex min-h-10 items-center gap-space-xs bg-surface-container-low hover:bg-error-container hover:text-on-error-container px-space-md py-space-xs rounded-lg transition-colors font-label-md text-label-md text-on-surface-variant disabled:opacity-50"
                >
                  <Icon name="logout" size={18} />
                  <span className="hidden md:inline">End session</span>
                </button>
              </>
            )}
          </div>
        </div>
      </header>
      {isResumeOpen && token && (
        <ResumeModal token={token} expiresAt={me.data?.expires_at ?? null} onClose={() => setIsResumeOpen(false)} />
      )}
    </>
    );
}
