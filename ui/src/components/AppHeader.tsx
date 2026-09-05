"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import type { DigestOut } from "@/api/types";
import { useHealth } from "@/hooks/useHealth";
import { useMe } from "@/hooks/useMe";
import { useSession } from "@/hooks/useSession";
import { formatClock, formatRelative } from "@/lib/format";
import { Icon } from "./Icon";
import { ResumeModal } from "./ResumeModal";

function NavLink({ href, children }: { href: string; children: string }) {
  const isActive = usePathname() === href;
  return (
    <Link
      href={href}
      aria-current={isActive ? "page" : undefined}
      className={`px-space-md py-space-xs rounded transition-colors ${
        isActive
          ? "bg-surface-container text-on-surface font-headline-sm text-headline-sm"
          : "font-label-lg text-label-lg text-on-surface-variant hover:text-on-surface"
      }`}
    >
      {children}
    </Link>
  );
}

function ProviderStrip({ digest }: { digest?: DigestOut }) {
  const [isDismissed, setIsDismissed] = useState(false);
  const health = useHealth(true);
  if (isDismissed || !health.data) return null;

  const failing = health.data.providers.filter((p) => p.circuit_state !== "closed");
  const isDegraded = failing.length > 0 || digest?.providers_degraded === true;
  const lastRefresh = health.data.scheduler.last_refresh_at;

  return (
    <div
      className={`w-full px-gutter-desktop py-space-xs ${
        isDegraded ? "bg-tertiary-fixed/60 text-on-tertiary-fixed" : "bg-secondary-container text-on-secondary-fixed"
      }`}
    >
      <div className="max-w-7xl mx-auto w-full flex items-center justify-between gap-space-md">
        <div className="flex items-center gap-space-sm min-w-0">
          <Icon name={isDegraded ? "warning" : "bolt"} size={16} className={isDegraded ? "text-tertiary" : "text-primary"} />
          <span className="font-label-sm text-label-sm uppercase tracking-wider">
            {isDegraded ? "Provider degraded" : "Providers normal"}
          </span>
          <span className="hidden sm:inline font-body-sm text-body-sm text-secondary truncate">
            {isDegraded
              ? `• ${failing.map((p) => p.provider).join(", ")} circuit ${failing[0]?.circuit_state ?? "open"}; last known good quotes served`
              : `• Yahoo + BSE circuits closed${lastRefresh ? ` • last refresh ${formatRelative(lastRefresh)}` : " • no refresh yet this session"}`}
          </span>
        </div>
        <div className="flex items-center gap-space-md">
          <span className="font-label-sm text-label-sm text-secondary hidden md:inline">
            Redis {health.data.redis} • DB {health.data.db}
          </span>
          <button
            type="button"
            onClick={() => setIsDismissed(true)}
            aria-label="Dismiss provider status"
            className="font-label-sm text-label-sm text-secondary hover:text-on-surface"
          >
            <Icon name="close" size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

export function AppHeader({ digest }: { digest?: DigestOut }) {
  const router = useRouter();
  const { token, end } = useSession();
  const me = useMe(Boolean(token));
  const [isResumeOpen, setIsResumeOpen] = useState(false);

  function endSession() {
    if (!window.confirm("End this session? The watchlist and rules on the server are deleted.")) return;
    end.mutate(undefined, { onSettled: () => router.replace("/") });
  }

  const marketLabel =
    digest?.market_status === "open" ? "Market Open" : digest?.market_status === "pre_open" ? "Pre-open" : "Market Closed";

  return (
    <header className="sticky top-0 z-40 bg-surface-container-lowest/90 backdrop-blur-md shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
      <ProviderStrip digest={digest} />
      <div className="h-16 max-w-7xl mx-auto px-margin-mobile md:px-margin-tablet lg:px-margin-desktop flex items-center justify-between gap-space-md">
        <div className="flex items-center gap-space-xl">
          <Link href="/watchlist" className="flex items-center gap-space-sm">
            <span className="w-8 h-8 rounded-lg bg-primary-container flex items-center justify-center text-on-primary-fixed">
              <Icon name="candlestick_chart" size={20} />
            </span>
            <span className="font-headline-sm text-headline-sm text-on-surface hidden sm:inline">
              Smart Market Watchlist
            </span>
          </Link>
          <nav className="flex items-center gap-space-xs bg-surface-container-low p-space-2xs rounded-lg">
            <NavLink href="/watchlist">Watchlist</NavLink>
            <NavLink href="/evidence">Evidence</NavLink>
          </nav>
        </div>
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
              <Icon name="person" size={18} className="text-on-primary" />
            </div>
            <span className="font-label-sm text-label-sm text-on-surface pr-space-xs hidden sm:inline">
              {me.data?.display_name ?? "…"}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setIsResumeOpen(true)}
            className="hidden sm:flex items-center gap-space-xs bg-surface-container-lowest px-space-md py-space-xs rounded-lg shadow-[0_1px_3px_rgba(15,23,42,0.04)] hover:bg-surface-container-low transition-colors font-label-md text-label-md text-on-surface"
          >
            <Icon name="qr_code_2" size={18} className="text-primary" />
            <span>Open on phone</span>
          </button>
          <button
            type="button"
            onClick={endSession}
            disabled={end.isPending}
            className="flex items-center gap-space-xs bg-surface-container-low hover:bg-error-container hover:text-on-error-container px-space-md py-space-xs rounded-lg transition-colors font-label-md text-label-md text-on-surface-variant disabled:opacity-50"
          >
            <Icon name="logout" size={18} />
            <span className="hidden md:inline">End session</span>
          </button>
        </div>
      </div>
      {isResumeOpen && token && (
        <ResumeModal token={token} expiresAt={me.data?.expires_at ?? null} onClose={() => setIsResumeOpen(false)} />
      )}
    </header>
  );
}
