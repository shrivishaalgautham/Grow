"use client";

import { useState } from "react";
import type { Item } from "@/api/types";
import { formatInr, formatSignedPercent, stripSuffix } from "@/lib/format";
import { freshnessText } from "./FreshnessTag";
import { Icon } from "./Icon";

const PAGE_SIZE = 6;

export function QuietTable({
  items,
  onOpen,
  onRemove,
}: {
  items: Item[];
  onOpen: (symbol: string) => void;
  onRemove: (symbol: string) => void;
}) {
  const [requestedPage, setRequestedPage] = useState(1);
  if (items.length === 0) return null;

  const pageCount = Math.ceil(items.length / PAGE_SIZE);
  const page = Math.min(requestedPage, pageCount);
  const firstIndex = (page - 1) * PAGE_SIZE;
  const visible = items.slice(firstIndex, firstIndex + PAGE_SIZE);

  return (
    <section className="space-y-space-sm pt-space-md">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-headline-md text-headline-md text-on-surface">Quiet watchlist items</h2>
          <p className="font-body-sm text-body-sm text-secondary">
            {items.length} {items.length === 1 ? "stock" : "stocks"} moved less than their own noise
          </p>
        </div>
        <span className="font-label-sm text-label-sm text-secondary">Floor 0.75% • z ≥ 2 against peers</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-space-md">
        {visible.map((item) => (
          <article
            key={item.symbol}
            className="bg-surface-container-lowest rounded-xl p-space-lg shadow-sm hover:shadow-md transition-shadow flex flex-col gap-space-sm"
          >
            <div className="flex items-start justify-between gap-space-sm">
              <div className="min-w-0">
                <button
                  type="button"
                  onClick={() => onOpen(item.symbol)}
                  className="inline-flex min-h-10 min-w-10 items-center font-headline-sm text-headline-sm text-on-surface hover:underline"
                >
                  {stripSuffix(item.symbol)}
                </button>
                <p className="font-body-sm text-body-sm text-secondary truncate">{item.name}</p>
              </div>
              <div className="text-right shrink-0">
                <div className="font-metric-tabular text-metric-tabular text-on-surface tabular">{formatInr(item.quote.price)}</div>
                <div
                  className={`font-metric-tabular text-metric-tabular tabular ${item.today_change_pct >= 0 ? "text-primary" : "text-tertiary"}`}
                >
                  {formatSignedPercent(item.today_change_pct)} today
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between gap-space-sm font-label-sm text-label-sm text-secondary">
              <span>Stock-specific</span>
              <span className="font-metric-tabular text-metric-tabular tabular">{formatSignedPercent(item.residual_pct)}</span>
            </div>

            <span className="inline-flex items-center gap-space-2xs self-start font-label-sm text-label-sm text-secondary bg-surface-container px-space-sm py-space-2xs rounded-full">
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${item.quote.confidence === "fresh" ? "bg-primary" : "bg-secondary"}`} />
              {freshnessText(item.quote)}
            </span>

            <div className="flex items-center gap-space-xs mt-auto pt-space-2xs">
              <button
                type="button"
                onClick={() => onOpen(item.symbol)}
                className="min-h-10 px-space-md py-space-2xs bg-surface-container-low hover:bg-surface-container text-on-surface font-label-sm text-label-sm rounded-lg transition-colors"
              >
                Details
              </button>
              <button
                type="button"
                onClick={() => onRemove(item.symbol)}
                className="min-h-10 px-space-md py-space-2xs text-secondary hover:text-tertiary font-label-sm text-label-sm rounded-lg transition-colors"
              >
                Remove
              </button>
            </div>
          </article>
        ))}
      </div>

      {pageCount > 1 && (
        <nav
          aria-label="Quiet watchlist pages"
          className="flex flex-wrap items-center justify-between gap-space-sm pt-space-2xs"
        >
          <span className="font-label-sm text-label-sm text-secondary">
            Showing {firstIndex + 1}–{firstIndex + visible.length} of {items.length} quiet positions
          </span>
          <div className="flex flex-wrap items-center gap-space-2xs">
            <button
              type="button"
              aria-label="Previous page"
              disabled={page === 1}
              onClick={() => setRequestedPage(page - 1)}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container-low transition-colors disabled:opacity-50 disabled:hover:bg-transparent"
            >
              <Icon name="arrow_back" size={16} />
            </button>
            {Array.from({ length: pageCount }, (_, index) => index + 1).map((number) => (
              <button
                key={number}
                type="button"
                aria-label={`Page ${number}`}
                aria-current={number === page ? "page" : undefined}
                onClick={() => setRequestedPage(number)}
                className={`w-8 h-8 rounded-lg font-label-sm text-label-sm transition-colors ${
                  number === page
                    ? "bg-surface-container text-on-surface font-bold"
                    : "text-secondary hover:bg-surface-container-low"
                }`}
              >
                {number}
              </button>
            ))}
            <button
              type="button"
              aria-label="Next page"
              disabled={page === pageCount}
              onClick={() => setRequestedPage(page + 1)}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container-low transition-colors disabled:opacity-50 disabled:hover:bg-transparent"
            >
              <Icon name="arrow_forward" size={16} />
            </button>
          </div>
        </nav>
      )}
    </section>
  );
}
