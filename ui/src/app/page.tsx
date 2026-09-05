"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { isRateLimited, isSessionGone } from "@/api/errors";
import { resumeTokenFromUrl } from "@/api/session";
import { Icon } from "@/components/Icon";
import type { IconName } from "@/components/icons";
import { useHealthProbe } from "@/hooks/useHealthProbe";
import { useVerifyEmail } from "@/hooks/useNotifications";
import { useSession } from "@/hooks/useSession";
import { formatRetryAfter } from "@/lib/format";

const SAMPLE_SYMBOLS = [
  "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "TMPV",
  "MARUTI", "SUNPHARMA", "ITC", "LT", "BHARTIARTL", "ADANIENT",
];
const NAME_PATTERN = /^[a-z0-9_-]{3,32}$/;

function Notice({
  icon,
  tone,
  title,
  children,
  aside,
}: {
  icon: IconName;
  tone: "info" | "warn" | "limit";
  title: string;
  children: string;
  aside?: string;
}) {
  const box = {
    info: "bg-secondary-container text-on-secondary-fixed",
    warn: "bg-tertiary-fixed text-on-tertiary-fixed",
    limit: "bg-surface-container-high text-on-surface",
  }[tone];
  const iconTone = tone === "info" ? `text-primary${icon === "progress_activity" ? " animate-spin" : ""}` : "text-tertiary";
  return (
    <div role="status" className={`flex items-start gap-space-sm p-space-sm rounded-lg ${box}`}>
      <Icon name={icon} size={20} className={`${iconTone} mt-0.5`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-space-sm">
          <p className="font-label-md text-label-md font-bold">{title}</p>
          {aside && <span className="font-metric-tabular text-metric-tabular text-tertiary">{aside}</span>}
        </div>
        <p className="font-body-sm text-body-sm opacity-80">{children}</p>
      </div>
    </div>
  );
}

function StartScreen() {
  const router = useRouter();
  const params = useSearchParams();
  const { token, ready, start, adoptToken } = useSession();
  const probe = useHealthProbe();
  const [displayName, setDisplayName] = useState("");
  const isResuming = ready && resumeTokenFromUrl() !== null;
  const isExpiredArrival = params.get("expired") === "1";
  const verifyToken = params.get("verify");
  const verify = useVerifyEmail();

  useEffect(() => {
    if (verifyToken) verify.mutate(verifyToken);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [verifyToken]);

  useEffect(() => {
    const resumeToken = resumeTokenFromUrl();
    if (resumeToken) adoptToken(resumeToken);
  }, [adoptToken]);

  useEffect(() => {
    if (ready && token && !verifyToken) router.replace("/watchlist");
  }, [ready, token, router, verifyToken]);

  const name = displayName.trim().toLowerCase();
  const isNameValid = name === "" || NAME_PATTERN.test(name);
  const isBusy = !ready || isResuming || (Boolean(token) && !verifyToken) || start.isPending || start.isSuccess;

  function begin(startWithSample: boolean) {
    if (!isNameValid) return;
    start.mutate({ start_with_sample: startWithSample, ...(name ? { display_name: name } : {}) });
  }

  return (
    <main className="w-full max-w-lg bg-surface-container-lowest rounded-xl shadow-[0_4px_20px_rgba(15,23,42,0.06)] p-space-2xl">
      <div className="flex flex-col w-full">
        <div className="flex flex-col items-center text-center space-y-space-sm mb-space-xl">
          <div className="inline-flex items-center gap-space-xs px-space-md py-space-2xs rounded-full bg-surface-container text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider mb-space-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-primary-container animate-pulse" />
            Since you last looked
          </div>
          <div className="flex items-center gap-space-sm">
            <div className="w-10 h-10 rounded-xl bg-primary-container flex items-center justify-center text-on-primary-fixed shadow-sm">
              <Icon name="candlestick_chart" size={24} />
            </div>
            <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">Smart Market Watchlist</h1>
          </div>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-sm pt-space-xs">
            What changed since you last looked, and whether it is the stock or the market.
          </p>
        </div>

        <div className="mb-space-lg space-y-space-sm">
          {(isResuming || start.isPending || start.isSuccess) && (
            <Notice icon="progress_activity" tone="info" title="Opening your watchlist…">
              {isResuming ? "Storing the resume token and removing it from the address bar." : "Creating the session on the server."}
            </Notice>
          )}
          {verify.isSuccess && (
            <Notice icon="mark_email_read" tone="info" title={`Alerts confirmed for ${verify.data.address_masked}`}>
              {token ? "Your session on this device is intact; open the watchlist to continue." : "You can close this tab, or start a session here."}
            </Notice>
          )}
          {verify.isError && (
            <Notice icon="error_outline" tone="warn" title="That confirmation link is invalid or expired">
              Request a new link from the alerts panel on the watchlist page.
            </Notice>
          )}
          {isExpiredArrival && !isBusy && (
            <Notice icon="lock_reset" tone="warn" title="Your session has expired">
              Sessions last 30 days. Start a new one below; nothing is looked up by name.
            </Notice>
          )}
          {isRateLimited(start.error) && (
            <Notice icon="speed" tone="limit" title="Rate limit reached (10 sessions per hour per IP)" aside={formatRetryAfter(start.error.retryAfterSeconds ?? 60)}>
              Existing session links keep working; only new session creation is paused.
            </Notice>
          )}
          {start.isError && !isRateLimited(start.error) && !isSessionGone(start.error) && (
            <Notice icon="error_outline" tone="warn" title="Could not start a session">
              {start.error.message}
            </Notice>
          )}
        </div>

        <div className="bg-surface-container-low rounded-xl p-space-xl shadow-sm mb-space-xl">
          <form className="flex flex-col space-y-space-lg" onSubmit={(event) => event.preventDefault()}>
            <div className="flex flex-col space-y-space-xs">
              <div className="flex justify-between items-center">
                <label htmlFor="displayName" className="font-label-md text-label-md text-on-surface font-semibold">Display name</label>
                <span className="font-label-sm text-label-sm text-outline">Optional</span>
              </div>
              <div className="relative flex items-center">
                <Icon name="alternate_email" size={20} className="absolute left-space-md text-outline pointer-events-none" />
                <input
                  id="displayName"
                  type="text"
                  value={displayName}
                  maxLength={32}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="e.g. nse_trader_42"
                  aria-invalid={!isNameValid}
                  className="w-full h-11 pl-10 pr-space-md bg-surface-container-lowest text-on-surface font-body-md text-body-md rounded-lg placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary-container"
                />
              </div>
              <p className={`font-body-sm text-body-sm flex items-center gap-space-2xs pt-space-2xs ${isNameValid ? "text-on-surface-variant" : "text-tertiary"}`}>
                <Icon name="info" size={14} className="text-outline" />
                3–32 chars, lowercase, digits, hyphen or underscore. Label only: sessions are never looked up by name.
              </p>
            </div>
            <div className="flex flex-col space-y-space-sm pt-space-xs">
              <button
                type="button"
                onClick={() => begin(true)}
                disabled={isBusy || !isNameValid}
                className="w-full flex items-center justify-between px-space-lg py-space-md bg-primary-container text-on-primary-fixed rounded-lg font-label-lg text-label-lg font-bold shadow-sm hover:opacity-95 active:scale-[0.99] transition-all disabled:opacity-60"
              >
                <span className="flex flex-col text-left">
                  <span className="flex items-center gap-space-xs">
                    Start with a sample watchlist
                    <Icon name="bolt" size={18} />
                  </span>
                  <span className="font-body-sm text-body-sm font-normal text-on-primary-fixed-variant">
                    12 NSE names, last review backdated 7 days so the digest is populated
                  </span>
                </span>
                <Icon name="arrow_forward" size={20} />
              </button>
              <button
                type="button"
                onClick={() => begin(false)}
                disabled={isBusy || !isNameValid}
                className="w-full flex items-center justify-center gap-space-xs py-space-md bg-surface-container-lowest text-on-surface rounded-lg font-label-lg text-label-lg font-semibold hover:bg-surface-container-high transition-colors disabled:opacity-60"
              >
                <Icon name="add_circle_outline" size={18} className="text-outline" />
                Start empty
              </button>
            </div>
          </form>
        </div>

        <div className="flex items-center justify-between px-space-md py-space-sm bg-surface-container-low rounded-lg mb-space-lg">
          <div className="flex items-center gap-space-xs">
            <span className={`w-2 h-2 rounded-full ${probe.data?.ok ? "bg-primary-container" : probe.data ? "bg-tertiary" : "bg-secondary"}`} />
            <span className="font-label-sm text-label-sm text-on-surface font-semibold">Silent health check:</span>
            <span className="font-body-sm text-body-sm text-on-surface-variant">
              {probe.data ? (probe.data.ok ? "API reachable" : "API unreachable") : "checking…"}
            </span>
          </div>
          <div className="flex items-center gap-space-2xs text-outline font-label-sm text-label-sm">
            <Icon name="sensors" size={14} />
            <span>{probe.data ? `${probe.data.latencyMs}ms` : "—"}</span>
          </div>
        </div>

        <div className="p-space-md bg-surface-container-lowest rounded-xl mb-space-xl flex flex-col space-y-space-sm border border-surface-container">
          <div className="flex justify-between items-center">
            <span className="font-label-sm text-label-sm text-outline uppercase tracking-wider">Sample watchlist</span>
            <span className="font-label-sm text-label-sm text-primary font-semibold bg-surface-container px-space-xs py-0.5 rounded">Nifty 100</span>
          </div>
          <div className="flex flex-wrap gap-space-xs">
            {SAMPLE_SYMBOLS.map((symbol) => (
              <span key={symbol} className="font-label-sm text-label-sm text-on-surface bg-surface-container-low px-space-sm py-space-2xs rounded">
                {symbol}
              </span>
            ))}
          </div>
          <p className="font-body-sm text-body-sm text-outline">
            Two IT names, two banks, two autos, so the peer panel has something to show.
          </p>
        </div>

        <div className="flex flex-col items-center text-center space-y-space-xs pt-space-xs">
          <p className="font-body-sm text-body-sm text-outline max-w-sm">
            No passwords. Anyone holding your session link has full access. Only a display name and a symbol list are
            stored. Demo data may be deleted without notice.
          </p>
          {token && verifyToken && (
            <Link href="/watchlist" className="inline-flex items-center gap-space-2xs font-label-lg text-label-lg text-primary hover:underline font-semibold">
              Open the watchlist
              <Icon name="arrow_forward" size={16} />
            </Link>
          )}
          <Link href="/evidence" className="inline-flex items-center gap-space-2xs font-label-sm text-label-sm text-primary hover:underline font-semibold pt-space-xs">
            Inspect the noise-reduction evidence
            <Icon name="arrow_outward" size={14} />
          </Link>
        </div>
      </div>
    </main>
  );
}

export default function StartPage() {
  return (
    <div className="min-h-dvh flex items-center justify-center p-margin-mobile">
      <Suspense fallback={null}>
        <StartScreen />
      </Suspense>
    </div>
  );
}
