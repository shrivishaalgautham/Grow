"use client";

import { useState } from "react";
import { isRateLimited } from "@/api/errors";
import { useRules } from "@/hooks/useRules";
import { formatRetryAfter, stripSuffix } from "@/lib/format";

export function RuleComposer({ enabled }: { enabled: boolean }) {
  const [text, setText] = useState("");
  const { list, compile, create, remove } = useRules(enabled);
  const compiled = compile.data;

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    compile.mutate(text.trim().slice(0, 200));
  }

  function confirm() {
    if (!compiled?.rule) return;
    create.mutate(
      { nl_text: text.trim().slice(0, 200), rule: compiled.rule },
      {
        onSuccess: () => {
          setText("");
          compile.reset();
        },
      },
    );
  }

  return (
    <section className="rounded-xl border border-line bg-surface p-5">
      <h2 className="text-sm font-semibold text-ink">Your rules</h2>
      <p className="mt-1 text-[13px] text-muted">
        Describe what you want flagged. It is compiled into a rule you can read
        before it goes live.
      </p>

      <form onSubmit={onSubmit} className="mt-4 flex flex-col gap-2 sm:flex-row">
        <input
          type="text"
          value={text}
          maxLength={200}
          onChange={(event) => setText(event.target.value)}
          placeholder="drops more than 2% against its peers on 3x volume"
          aria-label="Describe a rule in plain English"
          className="flex-1 rounded-lg border border-line bg-raised px-3.5 py-2.5 text-sm text-ink placeholder:text-faint focus:border-line-strong focus:outline-none"
        />
        <button
          type="submit"
          disabled={text.trim().length === 0 || compile.isPending}
          className="rounded-lg border border-line-strong px-4 py-2.5 text-xs font-semibold text-ink transition-colors hover:bg-raised disabled:opacity-40"
        >
          {compile.isPending ? "Compiling…" : "Preview"}
        </button>
      </form>

      {isRateLimited(compile.error) && (
        <p className="mt-3 text-[13px] text-delayed">
          Rule compiling is rate limited. Try again in{" "}
          {formatRetryAfter(compile.error.retryAfterSeconds ?? 60)}.
        </p>
      )}

      {compiled?.error && (
        <p className="mt-3 text-[13px] text-delayed">{compiled.error}</p>
      )}

      {compiled?.rule && compiled.preview && (
        <div className="mt-3 rounded-lg border border-rule/30 bg-rule/[0.06] px-3.5 py-3">
          <p className="text-[11px] tracking-wide text-faint uppercase">
            Compiles to
          </p>
          <p className="numeric mt-1 text-[13px] text-ink">{compiled.preview}</p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={confirm}
              disabled={create.isPending}
              className="rounded-md bg-ink px-3 py-1.5 text-xs font-semibold text-canvas disabled:opacity-50"
            >
              Save rule
            </button>
            <button
              type="button"
              onClick={() => compile.reset()}
              className="rounded-md border border-line px-3 py-1.5 text-xs text-muted hover:text-ink"
            >
              Discard
            </button>
          </div>
        </div>
      )}

      <ul className="mt-4 space-y-2">
        {list.data?.map((rule) => (
          <li
            key={rule.id}
            className="flex items-start justify-between gap-3 rounded-lg border border-line bg-raised px-3.5 py-2.5"
          >
            <div className="min-w-0">
              <p className="text-[13px] text-ink">{rule.nl_text}</p>
              <p className="numeric mt-0.5 text-[11px] text-faint">
                {rule.preview}
              </p>
              {rule.matched_today.length > 0 && (
                <p className="mt-1 text-[11px] text-rule">
                  Matched today: {rule.matched_today.map(stripSuffix).join(", ")}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={() => remove.mutate(rule.id)}
              className="shrink-0 text-[11px] text-faint transition-colors hover:text-down"
            >
              Delete
            </button>
          </li>
        ))}
      </ul>

      {list.data?.length === 0 && (
        <p className="mt-4 text-[13px] text-faint">
          No rules yet. The engine already flags peer-adjusted moves; rules are
          for the things only you care about.
        </p>
      )}
    </section>
  );
}
