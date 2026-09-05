"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { isFixtureMode } from "@/api/client";
import { resumeTokenFromUrl } from "@/api/session";
import { useSession } from "@/hooks/useSession";

export default function StartPage() {
  const router = useRouter();
  const { token, ready, start, adoptToken } = useSession();
  const [displayName, setDisplayName] = useState("");
  const isResuming = ready && resumeTokenFromUrl() !== null;

  useEffect(() => {
    const resumeToken = resumeTokenFromUrl();
    if (resumeToken) adoptToken(resumeToken);
  }, [adoptToken]);

  useEffect(() => {
    if (ready && token) router.replace("/watchlist");
  }, [ready, token, router]);

  const name = displayName.trim().toLowerCase();
  const nameIsValid = name === "" || /^[a-z0-9_-]{3,32}$/.test(name);
  const busy = start.isPending || start.isSuccess;

  if (!ready || isResuming || token) {
    return (
      <main className="flex min-h-dvh items-center justify-center px-6">
        <p className="text-sm text-muted">Opening your watchlist…</p>
      </main>
    );
  }

  function begin(startWithSample: boolean) {
    if (!nameIsValid) return;
    start.mutate({
      start_with_sample: startWithSample,
      ...(name ? { display_name: name } : {}),
    });
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-xl flex-col justify-center px-6 py-16">
      <p className="text-[11px] font-medium tracking-[0.18em] text-faint uppercase">
        NSE · Nifty 100 + Midcap 50
      </p>
      <h1 className="mt-3 text-3xl leading-tight font-semibold text-balance text-ink sm:text-4xl">
        What actually changed in your watchlist while you were away.
      </h1>
      <p className="mt-4 max-w-[52ch] text-[15px] leading-relaxed text-muted">
        Not every 2% move. Only the ones your stock made and its peer group did
        not — volatility-normalised, volume-confirmed, and ranked. Everything
        else stays below the fold.
      </p>

      <div className="mt-9">
        <label
          htmlFor="display-name"
          className="block text-[11px] font-medium tracking-wide text-faint uppercase"
        >
          Display name (optional)
        </label>
        <input
          id="display-name"
          type="text"
          value={displayName}
          maxLength={32}
          onChange={(event) => setDisplayName(event.target.value)}
          placeholder="lowercase letters, numbers, - and _"
          aria-invalid={!nameIsValid}
          aria-describedby={nameIsValid ? undefined : "display-name-error"}
          className="mt-2 w-full rounded-lg border border-line bg-surface px-3.5 py-2.5 text-sm text-ink placeholder:text-faint focus:border-line-strong focus:outline-none"
        />
        <p
          id="display-name-error"
          className={`mt-1.5 text-xs ${nameIsValid ? "text-faint" : "text-down"}`}
        >
          {nameIsValid
            ? "It is only a label. Sessions are never looked up by name."
            : "Use 3–32 characters: lowercase letters, numbers, hyphen or underscore."}
        </p>
      </div>

      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          onClick={() => begin(true)}
          disabled={busy || !nameIsValid}
          className="flex-1 rounded-lg bg-brand px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-strong disabled:opacity-50"
        >
          {busy ? "Setting up…" : "Start with a sample watchlist"}
        </button>
        <button
          type="button"
          onClick={() => begin(false)}
          disabled={busy || !nameIsValid}
          className="rounded-lg border border-line-strong px-4 py-3 text-sm font-medium text-muted transition-colors hover:bg-surface hover:text-ink disabled:opacity-50"
        >
          Start empty
        </button>
      </div>

      {start.isError && (
        <p role="alert" className="mt-3 text-[13px] text-down">
          {start.error.message}
        </p>
      )}

      <p className="mt-4 text-xs leading-relaxed text-faint">
        The sample loads 12 NSE names across four peer groups with your last
        review backdated a week, so there is something to read immediately.
      </p>

      <footer className="mt-12 border-t border-line pt-5 text-xs text-faint">
        <p>
          There is no password. Anyone holding your session link has full access
          to that watchlist. Only a display name and a list of symbols is
          stored.
        </p>
        <p className="mt-2">
          <Link href="/evidence" className="text-muted hover:text-ink">
            See the noise-reduction evidence
          </Link>
          {isFixtureMode && (
            <span className="ml-2 rounded border border-line px-1.5 py-0.5">
              fixture mode
            </span>
          )}
        </p>
      </footer>
    </main>
  );
}
