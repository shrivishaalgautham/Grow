"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { isRateLimited, isSessionGone } from "@/api/errors";
import { resumeTokenFromUrl } from "@/api/session";
import { Icon } from "@/components/Icon";
import type { IconName } from "@/components/icons";
import { SiteFooter } from "@/components/SiteFooter";
import { useHealthProbe } from "@/hooks/useHealthProbe";
import { useVerifyEmail } from "@/hooks/useNotifications";
import { useSession } from "@/hooks/useSession";
import { formatRetryAfter } from "@/lib/format";

const SAMPLE_SYMBOLS = [
  "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "TMPV",
  "MARUTI", "SUNPHARMA", "ITC", "LT", "BHARTIARTL", "ADANIENT",
];
const NAME_PATTERN = /^[a-z0-9_-]{3,32}$/;

const ALERT_LADDER = [
  { label: "Any ±2% move", alerts: 4188, tone: "bg-outline-variant" },
  { label: "Z-score on the raw return", alerts: 1372, tone: "bg-secondary" },
  { label: "Peer-residual engine", alerts: 311, tone: "bg-primary" },
];

const DIFFERENTIATORS: { icon: IconName; title: string; body: string }[] = [
  {
    icon: "grain",
    title: "The move is decomposed, not thresholded",
    body:
      "Each stock is measured against a behavioural peer cluster where one exists, and a beta-adjusted Nifty where it does not. What survives the peer move is the residual, scored in units of that stock's own residual volatility — so the bar is set by how quietly it usually trades, not by a number someone picked.",
  },
  {
    icon: "auto_graph",
    title: "Every signal names its mechanism",
    body:
      "EXCESS_MOVE, VOLUME_CONFIRMED, GAP, LEVEL_BREAK, SINCE_SEEN_MOVE. Each carries the numbers it fired on: a gap clears 2%, volume confirmation needs 1.5× the stock's normal, a move since you last looked has to clear 1.5% and twice the drift expected over that gap. You read why, not just that.",
  },
  {
    icon: "psychology",
    title: "Rules in English, compiled to something you can audit",
    body:
      "Describe a trigger — \"drops more than 2% against its peers on 3x volume\" — and it compiles to a bounded JSON condition you read and confirm before it saves. You can open the compiled rule. The model writes it; the engine, never the model, evaluates it.",
  },
  {
    icon: "troubleshoot",
    title: "What it suppressed is on the record",
    body:
      "The evidence page replays all three alert rules over the same stored bars and breaks the gap down: market-wide, below the floor, or inside the stock's own noise. It also lists the six days a percentage rule misses — raw moves under 1.8% whose peer-adjusted residual was over 2.8%.",
  },
];

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
  const { token, ready, start, adoptToken, signInWithGoogle } = useSession();
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
    <div className="w-full bg-surface-container-lowest rounded-xl shadow-[0_4px_20px_rgba(15,23,42,0.06)] p-space-xl md:p-space-2xl">
      <div className="flex flex-col space-y-space-xs mb-space-xl max-w-2xl">
        <span className="font-label-sm text-label-sm text-primary uppercase tracking-wider font-bold">Start a session</span>
        <h2 className="font-headline-md text-headline-md text-on-surface tracking-tight">Take a watchlist of your own</h2>
        <p className="font-body-md text-body-md text-on-surface-variant">
          No password, no email required. A session is a token in this browser that you can carry to your phone with a
          one-time link.
        </p>
      </div>

      <div className="space-y-space-sm empty:hidden mb-space-lg">
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

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-space-xl">
        <div className="lg:col-span-3 space-y-space-lg">
          <div className="space-y-space-md">
            <button
              type="button"
              onClick={signInWithGoogle}
              disabled={isBusy}
              className="w-full flex items-center justify-center gap-space-sm px-space-lg py-space-md bg-surface-container-lowest border border-surface-container text-on-surface rounded-lg font-label-lg text-label-lg font-semibold shadow-sm hover:bg-surface-container-low transition-colors disabled:opacity-60"
            >
              <Icon name="verified" size={20} className="text-primary" />
              Continue with Google
            </button>
            <div className="flex items-center gap-space-sm">
              <div className="h-px flex-1 bg-surface-container" />
              <span className="font-label-sm text-label-sm text-outline uppercase tracking-wider">or try it anonymously</span>
              <div className="h-px flex-1 bg-surface-container" />
            </div>
          </div>

          <div className="bg-surface-container-low rounded-xl p-space-xl shadow-sm">
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
              <div className="flex flex-col sm:flex-row gap-space-sm pt-space-xs">
                <button
                  type="button"
                  onClick={() => begin(true)}
                  disabled={isBusy || !isNameValid}
                  className="flex-1 flex items-center justify-between px-space-lg py-space-md bg-primary-container text-on-primary-fixed rounded-lg font-label-lg text-label-lg font-bold shadow-sm hover:opacity-95 active:scale-[0.99] transition-all disabled:opacity-60"
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
                  className="sm:w-48 shrink-0 flex items-center justify-center gap-space-xs py-space-md bg-surface-container-lowest text-on-surface rounded-lg font-label-lg text-label-lg font-semibold hover:bg-surface-container-high transition-colors disabled:opacity-60"
                >
                  <Icon name="add_circle_outline" size={18} className="text-outline" />
                  Start empty
                </button>
              </div>
            </form>
          </div>

          <p className="font-body-sm text-body-sm text-outline">
            No passwords. Anyone holding your session link has full access. Only a display name and a symbol list are
            stored. Demo data may be deleted without notice.
            {token && verifyToken && (
              <>
                {" "}
                <Link href="/watchlist" className="inline-flex items-center gap-space-2xs text-primary hover:underline font-semibold">
                  Open the watchlist
                  <Icon name="arrow_forward" size={14} />
                </Link>
              </>
            )}
          </p>
        </div>

        <div className="lg:col-span-2 space-y-space-md">
          <div className="flex items-center justify-between px-space-md py-space-sm bg-surface-container-low rounded-lg">
            <div className="flex items-center gap-space-xs min-w-0">
              <span className={`w-2 h-2 rounded-full shrink-0 ${probe.data?.ok ? "bg-primary-container" : probe.data ? "bg-tertiary" : "bg-secondary"}`} />
              <span className="font-label-sm text-label-sm text-on-surface font-semibold shrink-0">Silent health check:</span>
              <span className="font-body-sm text-body-sm text-on-surface-variant truncate">
                {probe.data ? (probe.data.ok ? "API reachable" : "API unreachable") : "checking…"}
              </span>
            </div>
            <div className="flex items-center gap-space-2xs text-outline font-label-sm text-label-sm shrink-0">
              <Icon name="sensors" size={14} />
              <span>{probe.data ? `${probe.data.latencyMs}ms` : "—"}</span>
            </div>
          </div>

          <div className="p-space-md bg-surface-container-lowest rounded-xl flex flex-col space-y-space-sm border border-surface-container">
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
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  const maxAlerts = ALERT_LADDER[0].alerts;

  return (
    <div className="min-h-dvh flex flex-col">
      <header className="w-full">
        <div className="max-w-6xl mx-auto px-margin-mobile md:px-margin-tablet lg:px-margin-desktop h-16 flex items-center justify-between gap-space-md">
          <span className="flex items-center gap-space-sm">
            <span className="w-8 h-8 rounded-lg bg-primary-container flex items-center justify-center text-on-primary-fixed">
              <Icon name="candlestick_chart" size={20} />
            </span>
            <span className="font-headline-sm text-headline-sm text-on-surface">Smart Market Watchlist</span>
          </span>
          <Link
            href="#start"
            className="font-label-md text-label-md text-on-surface-variant hover:text-on-surface transition-colors"
          >
            Start a session
          </Link>
        </div>
      </header>

      <main className="w-full flex-1 max-w-6xl mx-auto px-margin-mobile md:px-margin-tablet lg:px-margin-desktop">
        <section className="pt-space-2xl pb-space-3xl md:pt-space-3xl">
          <div className="max-w-3xl space-y-space-lg">
            <span className="inline-flex items-center gap-space-xs px-space-md py-space-2xs rounded-full bg-surface-container-low text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider">
              <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              Peer-relative signal engine · NSE
            </span>
            <h1 className="font-headline-xl text-headline-xl-mobile md:text-headline-xl text-on-surface tracking-tight">
              Most watchlists tell you a stock moved. This one tells you whether that was news, or just the market.
            </h1>
            <p className="font-body-lg text-body-lg text-on-surface-variant leading-relaxed">
              Every move is split into the part its peer group explains and the part left over. The leftover — the
              residual — is scored against that stock&rsquo;s own history, not a fixed percentage. So a 2% move on a day
              the sector ran 2% says nothing, and a 1.2% rise while its peers fell 2.6% is the one you get told about.
            </p>
            <div className="flex flex-col sm:flex-row gap-space-sm pt-space-xs">
              <Link
                href="/watchlist"
                className="inline-flex items-center justify-center gap-space-sm px-space-2xl py-space-md bg-primary-container text-on-primary-fixed rounded-lg font-label-lg text-label-lg font-bold shadow-sm hover:opacity-95 active:scale-[0.99] transition-all"
              >
                <Icon name="visibility" size={20} />
                See the live demo
                <Icon name="arrow_forward" size={18} />
              </Link>
              <Link
                href="#start"
                className="inline-flex items-center justify-center gap-space-xs px-space-xl py-space-md bg-surface-container-lowest text-on-surface rounded-lg font-label-lg text-label-lg font-semibold shadow-sm hover:bg-surface-container-low transition-colors"
              >
                Take one of your own
              </Link>
            </div>
            <p className="font-body-sm text-body-sm text-outline">
              The demo needs no signup: a real 12-stock NSE watchlist, read-only, with the decomposition and the
              signals live.
            </p>
          </div>
        </section>

        <section className="pb-space-3xl">
          <div className="bg-surface-container-lowest rounded-xl shadow-sm p-space-xl md:p-space-2xl space-y-space-lg">
            <div className="space-y-space-xs">
              <span className="font-label-sm text-label-sm text-primary uppercase tracking-wider font-bold">
                Replayed on 150 NSE symbols over 90 sessions
              </span>
              <h2 className="font-headline-md text-headline-md text-on-surface">
                Three ways to raise an alert on the same stored bars
              </h2>
            </div>
            <div className="space-y-space-md">
              {ALERT_LADDER.map((rule, index) => (
                <div key={rule.label} className="space-y-space-2xs">
                  <div className="flex items-baseline justify-between gap-space-md">
                    <span className={`font-label-md text-label-md ${index === 2 ? "text-on-surface font-bold" : "text-on-surface-variant"}`}>
                      {rule.label}
                    </span>
                    <span className={`font-metric-tabular text-metric-tabular tabular ${index === 2 ? "text-primary font-bold" : "text-secondary"}`}>
                      {rule.alerts.toLocaleString("en-IN")} alerts
                    </span>
                  </div>
                  <div className="w-full bg-surface-container h-2.5 rounded-full overflow-hidden">
                    <div className={`${rule.tone} h-full rounded-full`} style={{ width: `${(rule.alerts / maxAlerts) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
            <p className="font-body-md text-body-md text-on-surface-variant">
              Of the 3,877 alerts the engine drops, 2,140 go because the whole market was moving, 1,094 because the
              residual never cleared the floor, and 643 because the stock routinely moves that much anyway. It is not a
              quieter version of the same list — it is a different one.
            </p>
            <Link
              href="/evidence"
              className="inline-flex items-center gap-space-xs px-space-md py-space-xs bg-surface-container-low hover:bg-surface-container text-on-surface font-label-md text-label-md rounded-lg transition-colors"
            >
              <Icon name="troubleshoot" size={18} className="text-primary" />
              <span>Inspect the noise-reduction evidence</span>
              <Icon name="arrow_outward" size={14} />
            </Link>
          </div>
        </section>

        <section className="pb-space-3xl space-y-space-lg">
          <h2 className="font-headline-md text-headline-md text-on-surface">What it does that a price alert cannot</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-space-lg">
            {DIFFERENTIATORS.map((entry) => (
              <article key={entry.title} className="bg-surface-container-lowest rounded-xl shadow-sm p-space-xl space-y-space-sm">
                <span className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Icon name={entry.icon} size={22} className="text-primary" />
                </span>
                <h3 className="font-headline-sm text-headline-sm text-on-surface">{entry.title}</h3>
                <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">{entry.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="start" className="pb-space-3xl scroll-mt-space-xl">
          <Suspense fallback={null}>
            <StartScreen />
          </Suspense>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
