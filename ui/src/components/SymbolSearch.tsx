"use client";

import { useId, useRef, useState } from "react";
import { useSymbolSearch } from "@/hooks/useSymbolSearch";
import { stripSuffix } from "@/lib/format";

export function SymbolSearch({
  owned,
  onAdd,
  isAdding,
}: {
  owned: string[];
  onAdd: (symbol: string) => void;
  isAdding: boolean;
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);

  const { data, isFetching } = useSymbolSearch(query);
  const results = data ?? [];
  const isOpen = query.trim().length >= 2;

  function choose(symbol: string) {
    onAdd(symbol);
    setQuery("");
    setActive(0);
    inputRef.current?.focus();
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter" && results[active]) {
      event.preventDefault();
      if (!owned.includes(results[active].symbol)) choose(results[active].symbol);
    } else if (event.key === "Escape") {
      setQuery("");
    }
  }

  return (
    <div className="relative">
      <label htmlFor={`${listId}-input`} className="sr-only">
        Add a symbol to your watchlist
      </label>
      <input
        id={`${listId}-input`}
        ref={inputRef}
        type="search"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setActive(0);
        }}
        onKeyDown={onKeyDown}
        placeholder="Add a stock — try Hindalco, Titan or Wipro"
        autoComplete="off"
        role="combobox"
        aria-expanded={isOpen}
        aria-controls={listId}
        aria-autocomplete="list"
        className="w-full rounded-lg border border-line bg-surface px-3.5 py-2.5 text-sm text-ink placeholder:text-faint focus:border-line-strong focus:outline-none"
      />

      {isOpen && (
        <ul
          id={listId}
          role="listbox"
          aria-label="Symbol results"
          className="absolute z-20 mt-1.5 max-h-72 w-full overflow-auto rounded-lg border border-line-strong bg-raised py-1 shadow-2xl shadow-black/50"
        >
          {results.length === 0 && (
            <li className="px-3.5 py-3 text-[13px] text-faint">
              {isFetching
                ? "Searching the 150-symbol universe…"
                : "Nothing in the universe matches that. Only seeded NSE symbols can be added."}
            </li>
          )}

          {results.map((row, index) => {
            const alreadyOwned = owned.includes(row.symbol);
            return (
              <li key={row.symbol} role="option" aria-selected={index === active}>
                <button
                  type="button"
                  disabled={alreadyOwned || isAdding}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => choose(row.symbol)}
                  className={`flex w-full items-center justify-between gap-3 px-3.5 py-2 text-left transition-colors disabled:cursor-not-allowed ${index === active ? "bg-line" : ""}`}
                >
                  <span className="min-w-0">
                    <span className="numeric text-sm text-ink">
                      {stripSuffix(row.symbol)}
                    </span>
                    <span className="ml-2 text-xs text-muted">{row.name}</span>
                  </span>
                  <span className="shrink-0 text-[11px] text-faint">
                    {alreadyOwned ? "In watchlist" : row.industry}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
