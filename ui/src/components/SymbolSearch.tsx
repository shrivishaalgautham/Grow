"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useSymbolSearch } from "@/hooks/useSymbolSearch";
import { initials, stripSuffix } from "@/lib/format";
import { Icon } from "./Icon";

const CAP = 50;

export function SymbolSearch({
  owned,
  onAdd,
  isAdding,
  error,
}: {
  owned: string[];
  onAdd: (symbol: string) => void;
  isAdding: boolean;
  error: Error | null;
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const { data, isFetching } = useSymbolSearch(query);
  const results = data ?? [];
  const isOpen = query.trim().length >= 2;

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  function choose(symbol: string) {
    onAdd(symbol);
    setQuery("");
    setActive(0);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter" && results[active] && !owned.includes(results[active].symbol)) {
      event.preventDefault();
      choose(results[active].symbol);
    } else if (event.key === "Escape") {
      setQuery("");
    }
  }

  return (
    <section className="relative">
      <div className="bg-surface-container-lowest rounded-xl p-space-md shadow-sm">
        <div className="relative flex items-center">
          <Icon name="search" size={22} className="absolute left-space-md text-secondary" />
          <label htmlFor={`${listId}-input`} className="sr-only">Add a symbol to your watchlist</label>
          <input
            id={`${listId}-input`}
            ref={inputRef}
            type="text"
            value={query}
            autoComplete="off"
            role="combobox"
            aria-expanded={isOpen}
            aria-controls={listId}
            aria-autocomplete="list"
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
            }}
            onKeyDown={onKeyDown}
            placeholder="Search an NSE symbol or company (e.g. RELIANCE, Titan, Wipro)…"
            className="w-full pl-12 pr-28 py-space-md bg-surface-container-low focus:bg-surface-container-lowest text-on-surface rounded-lg font-body-md text-body-md placeholder:text-secondary outline-none ring-2 ring-primary/20 focus:ring-primary transition-all"
          />
          <div className="absolute right-space-md flex items-center gap-space-xs">
            <kbd className="hidden sm:inline-block px-space-xs py-space-2xs bg-surface-container rounded text-secondary font-label-sm text-label-sm">⌘K</kbd>
            <span className={`w-2 h-2 rounded-full ${isFetching ? "bg-secondary animate-pulse" : "bg-primary-container"}`} />
          </div>
        </div>

        {error && <p role="alert" className="mt-space-sm font-body-sm text-body-sm text-tertiary">{error.message}</p>}

        {isOpen && (
          <div className="mt-space-sm bg-surface-container-lowest rounded-xl shadow-xl overflow-hidden p-space-sm space-y-space-xs">
            <div className="flex items-center justify-between px-space-sm py-space-2xs font-label-sm text-label-sm text-secondary uppercase tracking-wider">
              <span>Search results &amp; universe check</span>
              <span>Top 10</span>
            </div>
            <ul id={listId} role="listbox" aria-label="Symbol results" className="space-y-space-xs">
              {results.length === 0 && (
                <li className="px-space-sm py-space-md font-body-sm text-body-sm text-secondary">
                  {isFetching ? "Searching the 150-symbol universe…" : "Nothing in the universe matches that. Only seeded NSE symbols can be added."}
                </li>
              )}
              {results.map((row, index) => {
                const isOwned = owned.includes(row.symbol);
                const isActive = index === active;
                return (
                  <li key={row.symbol} role="option" aria-selected={isActive}>
                    <div
                      onMouseEnter={() => setActive(index)}
                      className={`flex items-center justify-between p-space-sm rounded-lg transition-colors ${
                        isOwned ? "opacity-60" : isActive ? "bg-surface-container" : "bg-surface-container-low hover:bg-surface-container"
                      }`}
                    >
                      <div className="flex items-center gap-space-md min-w-0">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center font-headline-sm text-headline-sm ${isOwned ? "bg-surface-container text-secondary" : "bg-surface-container-highest text-primary"}`}>
                          {initials(row.symbol)}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-space-xs">
                            <span className="font-headline-sm text-headline-sm text-on-surface">{stripSuffix(row.symbol)}</span>
                            <span className="font-label-sm text-label-sm px-space-xs py-space-2xs bg-secondary-container text-on-secondary-fixed rounded truncate">{row.industry}</span>
                          </div>
                          <span className="font-body-sm text-body-sm text-secondary">{row.name} • NSE</span>
                        </div>
                      </div>
                      {isOwned ? (
                        <span className="font-label-sm text-label-sm bg-surface-container px-space-sm py-space-xs rounded text-secondary font-semibold shrink-0">Already in watchlist</span>
                      ) : (
                        <button
                          type="button"
                          disabled={isAdding}
                          onClick={() => choose(row.symbol)}
                          className="px-space-md py-space-xs bg-primary text-on-primary rounded-lg font-label-md text-label-md hover:bg-primary/90 transition-colors shrink-0 disabled:opacity-60"
                        >
                          Add
                        </button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
            <div className="mt-space-xs pt-space-xs flex flex-wrap items-center justify-between gap-space-sm px-space-sm bg-surface-container-low/70 rounded-lg py-space-xs">
              <div className="flex items-center gap-space-xs text-on-surface-variant font-label-sm text-label-sm">
                <Icon name={owned.length >= CAP ? "error_outline" : "inventory_2"} size={16} className={owned.length >= CAP ? "text-tertiary" : "text-primary"} />
                <span>{owned.length} of {CAP} slots filled</span>
              </div>
              <div className="flex items-center gap-space-xs text-secondary font-label-sm text-label-sm">
                <Icon name="info" size={16} />
                <span>Universe: Nifty 100 + Nifty Midcap 50</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
