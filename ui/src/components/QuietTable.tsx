"use client";

import { useState } from "react";
import type { Item } from "@/api/types";
import { formatInr, formatSignedPercent, stripSuffix } from "@/lib/format";
import { freshnessText } from "./FreshnessTag";

const PREVIEW_ROWS = 4;

export function QuietTable({
  items,
  onOpen,
  onRemove,
}: {
  items: Item[];
  onOpen: (symbol: string) => void;
  onRemove: (symbol: string) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  if (items.length === 0) return null;
  const visible = isExpanded ? items : items.slice(0, PREVIEW_ROWS);
  const hidden = items.length - visible.length;

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
      <div className="bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface-container-low text-secondary font-label-sm text-label-sm uppercase tracking-wider">
                <th className="py-space-sm px-space-md">Symbol</th>
                <th className="py-space-sm px-space-md">Company</th>
                <th className="py-space-sm px-space-md text-right">Price</th>
                <th className="py-space-sm px-space-md text-right">Today %</th>
                <th className="py-space-sm px-space-md text-right">Stock-specific %</th>
                <th className="py-space-sm px-space-md text-center">Freshness</th>
                <th className="py-space-sm px-space-md text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="text-on-surface font-body-md text-body-md">
              {visible.map((item) => (
                <tr key={item.symbol} className="hover:bg-surface-container-low/50 transition-colors">
                  <td className="py-space-md px-space-md font-headline-sm text-headline-sm">
                    <button type="button" onClick={() => onOpen(item.symbol)} className="hover:underline">{stripSuffix(item.symbol)}</button>
                  </td>
                  <td className="py-space-md px-space-md text-secondary font-body-sm text-body-sm">{item.name}</td>
                  <td className="py-space-md px-space-md text-right font-metric-tabular text-metric-tabular tabular">{formatInr(item.quote.price)}</td>
                  <td className={`py-space-md px-space-md text-right font-metric-tabular text-metric-tabular tabular ${item.today_change_pct >= 0 ? "text-primary" : "text-tertiary"}`}>
                    {formatSignedPercent(item.today_change_pct)}
                  </td>
                  <td className="py-space-md px-space-md text-right font-metric-tabular text-metric-tabular text-secondary tabular">{formatSignedPercent(item.residual_pct)}</td>
                  <td className="py-space-md px-space-md text-center">
                    <span className="inline-flex items-center gap-space-2xs font-label-sm text-label-sm text-secondary bg-surface-container px-space-sm py-space-2xs rounded-full whitespace-nowrap">
                      <span className={`w-1.5 h-1.5 rounded-full ${item.quote.confidence === "fresh" ? "bg-primary" : "bg-secondary"}`} />
                      {freshnessText(item.quote)}
                    </span>
                  </td>
                  <td className="py-space-md px-space-md text-right">
                    <div className="inline-flex items-center gap-space-xs">
                      <button type="button" onClick={() => onOpen(item.symbol)} className="px-space-sm py-space-2xs text-secondary hover:text-on-surface font-label-sm text-label-sm">Details</button>
                      <button type="button" onClick={() => onRemove(item.symbol)} className="px-space-sm py-space-2xs text-secondary hover:text-tertiary font-label-sm text-label-sm">Remove</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {items.length > PREVIEW_ROWS && (
          <div className="px-space-md py-space-sm bg-surface-container-low flex items-center justify-between text-secondary font-label-sm text-label-sm">
            <span>Displaying {visible.length} of {items.length} quiet positions</span>
            <button type="button" onClick={() => setIsExpanded((v) => !v)} className="font-bold text-on-surface hover:underline">
              {isExpanded ? "Show fewer ↑" : `View remaining ${hidden} ↓`}
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
