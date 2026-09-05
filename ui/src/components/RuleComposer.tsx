"use client";

import { useState } from "react";
import { isRateLimited } from "@/api/errors";
import type { Rule } from "@/api/types";
import { useRules } from "@/hooks/useRules";
import { formatRetryAfter, stripSuffix } from "@/lib/format";
import { Icon } from "./Icon";

const MAX_RULES = 10;

function conditionSummary(rule: Rule) {
  const scope = rule.symbols === "all" ? "Any watched stock" : rule.symbols.map(stripSuffix).join(", ");
  const conditions = rule.all.map((c) => `${c.field} ${c.op} ${String(c.value)}`).join(" • ");
  return `Scope: ${scope} • ${conditions}`;
}

export function RuleComposer({ enabled }: { enabled: boolean }) {
  const [text, setText] = useState("");
  const { list, compile, create, remove } = useRules(enabled);
  const compiled = compile.data;
  const rules = list.data ?? [];

  function preview(event: React.FormEvent) {
    event.preventDefault();
    if (text.trim()) compile.mutate(text.trim().slice(0, 200));
  }

  function save() {
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
    <section className="bg-surface-container-lowest rounded-xl p-space-xl md:p-space-2xl shadow-sm space-y-space-lg">
      <div className="flex items-center justify-between gap-space-md">
        <div className="space-y-space-2xs">
          <div className="flex items-center gap-space-xs text-primary font-label-sm text-label-sm uppercase tracking-wider font-bold">
            <Icon name="psychology" size={18} />
            <span>Natural-language rules</span>
          </div>
          <h2 className="font-headline-md text-headline-md text-on-surface">Your rules</h2>
          <p className="font-body-sm text-body-sm text-secondary">
            Describe a trigger in plain English. It compiles to a bounded rule you read and confirm before it runs; the model never evaluates it.
          </p>
        </div>
        <span className="px-space-sm py-space-2xs bg-surface-container text-secondary font-label-sm text-label-sm rounded shrink-0">
          {rules.length} of {MAX_RULES}
        </span>
      </div>

      <form onSubmit={preview} className="space-y-space-sm">
        <div className="flex flex-col sm:flex-row gap-space-sm">
          <input
            type="text"
            value={text}
            maxLength={200}
            onChange={(event) => setText(event.target.value)}
            placeholder="drops more than 2% against its peers on 3x volume"
            aria-label="Describe a rule in plain English"
            className="flex-1 px-space-md py-space-sm bg-surface-container-low text-on-surface rounded-lg font-body-md text-body-md outline-none ring-2 ring-primary/20 focus:ring-primary placeholder:text-secondary"
          />
          <button
            type="submit"
            disabled={text.trim().length === 0 || compile.isPending}
            className="px-space-xl py-space-sm bg-primary hover:bg-primary/90 text-on-primary font-label-lg text-label-lg rounded-lg shadow-sm transition-colors flex items-center justify-center gap-space-xs shrink-0 disabled:opacity-50"
          >
            <Icon name="rule" size={18} />
            <span>{compile.isPending ? "Compiling…" : "Preview rule"}</span>
          </button>
        </div>

        {isRateLimited(compile.error) && (
          <p role="alert" className="font-body-sm text-body-sm text-tertiary">
            Rule compiling is rate limited (5 per hour). Try again in {formatRetryAfter(compile.error.retryAfterSeconds ?? 60)}.
          </p>
        )}
        {compile.error && !isRateLimited(compile.error) && (
          <p role="alert" className="font-body-sm text-body-sm text-tertiary">{compile.error.message}</p>
        )}
        {compiled?.error && <p role="alert" className="font-body-sm text-body-sm text-tertiary">{compiled.error}</p>}

        {compiled?.rule && compiled.preview && (
          <div className="p-space-md bg-surface-container-low rounded-xl space-y-space-md">
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-space-md">
              <div className="space-y-space-xs min-w-0">
                <div className="font-label-sm text-label-sm uppercase text-primary font-bold tracking-wider flex items-center gap-space-2xs">
                  <Icon name="verified" size={16} />
                  <span>Compiled preview — confirm before it runs</span>
                </div>
                <p className="font-body-md text-body-md text-on-surface font-semibold">&ldquo;{compiled.preview}&rdquo;</p>
                <p className="font-body-sm text-body-sm text-secondary">{conditionSummary(compiled.rule)}</p>
              </div>
              <div className="flex items-center gap-space-sm shrink-0">
                <button
                  type="button"
                  onClick={save}
                  disabled={create.isPending}
                  className="px-space-md py-space-xs bg-primary-container text-on-primary-fixed hover:bg-primary-fixed-dim font-label-md text-label-md rounded-lg font-bold transition-colors disabled:opacity-60"
                >
                  {create.isPending ? "Saving…" : "Save rule"}
                </button>
                <button type="button" onClick={() => compile.reset()} className="px-space-md py-space-xs bg-surface-container hover:bg-surface-container-high text-on-surface font-label-md text-label-md rounded-lg transition-colors">
                  Discard
                </button>
              </div>
            </div>
            {create.error && <p role="alert" className="font-body-sm text-body-sm text-tertiary">{create.error.message}</p>}
            <details className="group text-secondary font-mono text-body-sm">
              <summary className="cursor-pointer font-label-sm text-label-sm text-primary hover:underline flex items-center gap-space-2xs list-none">
                <Icon name="chevron_right" size={16} className="group-open:rotate-90 transition-transform" />
                <span>Inspect the compiled rule JSON</span>
              </summary>
              <pre className="mt-space-sm p-space-sm bg-surface-container-lowest rounded-lg overflow-x-auto text-[12px] text-on-surface-variant leading-relaxed">
                {JSON.stringify(compiled.rule, null, 2)}
              </pre>
            </details>
          </div>
        )}
      </form>

      <div className="space-y-space-sm pt-space-xs">
        <div className="font-label-sm text-label-sm uppercase tracking-wider text-secondary">Active rules ({rules.length})</div>
        {rules.length === 0 && (
          <p className="font-body-sm text-body-sm text-secondary">
            No rules yet. The engine already flags peer-adjusted moves; rules are for the things only you care about.
          </p>
        )}
        <div className="space-y-space-xs">
          {rules.map((rule) => (
            <div key={rule.id} className="p-space-md bg-surface-container-low rounded-lg flex items-center justify-between gap-space-md">
              <div className="flex items-center gap-space-md min-w-0">
                <Icon name="tune" size={20} className={rule.matched_today.length > 0 ? "text-primary" : "text-secondary"} />
                <div className="min-w-0">
                  <div className="font-label-md text-label-md text-on-surface truncate">{rule.preview}</div>
                  <div className="font-body-sm text-body-sm text-secondary truncate">&ldquo;{rule.nl_text}&rdquo;</div>
                </div>
              </div>
              <div className="flex items-center gap-space-md shrink-0">
                {rule.matched_today.length > 0 ? (
                  <span className="inline-flex items-center gap-space-2xs px-space-sm py-space-2xs bg-primary-container/20 text-on-primary-container font-label-sm text-label-sm font-bold rounded-full">
                    <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                    Matched today: {rule.matched_today.map(stripSuffix).join(", ")}
                  </span>
                ) : (
                  <span className="hidden sm:inline-flex px-space-sm py-space-2xs bg-surface-container text-secondary font-label-sm text-label-sm rounded-full">No match today</span>
                )}
                <button type="button" onClick={() => remove.mutate(rule.id)} aria-label="Delete rule" className="text-secondary hover:text-tertiary transition-colors">
                  <Icon name="delete" size={18} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
