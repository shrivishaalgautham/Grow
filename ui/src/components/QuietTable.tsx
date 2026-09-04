"use client";

import type { Item } from "@/api/types";
import { FreshnessBadge } from "./FreshnessBadge";
import { formatInr, formatSignedPercent, stripSuffix } from "@/lib/format";

export function QuietTable({
  items,
  onOpen,
  onRemove,
}: {
  items: Item[];
  onOpen: (symbol: string) => void;
  onRemove: (symbol: string) => void;
}) {
  if (items.length === 0) return null;

  return (
    <div className="overflow-hidden rounded-xl border border-line bg-surface">
      <table className="w-full border-collapse text-sm">
        <caption className="border-b border-line px-4 py-3 text-left">
          <span className="text-sm font-medium text-ink">
            Quiet · {items.length}
          </span>
          <span className="ml-2 text-xs text-muted">
            moved less than their own noise
          </span>
        </caption>
        <thead>
          <tr className="text-[11px] tracking-wide text-faint uppercase">
            <th scope="col" className="px-4 py-2 text-left font-medium">
              Symbol
            </th>
            <th scope="col" className="px-4 py-2 text-right font-medium">
              Price
            </th>
            <th scope="col" className="px-4 py-2 text-right font-medium">
              Today
            </th>
            <th
              scope="col"
              className="hidden px-4 py-2 text-right font-medium sm:table-cell"
            >
              Stock-specific
            </th>
            <th
              scope="col"
              className="hidden px-4 py-2 text-left font-medium md:table-cell"
            >
              Quote
            </th>
            <th scope="col" className="px-4 py-2 text-right font-medium">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.symbol}
              className="border-t border-line/70 transition-colors hover:bg-raised"
            >
              <th scope="row" className="px-4 py-2.5 text-left font-normal">
                <button
                  type="button"
                  onClick={() => onOpen(item.symbol)}
                  className="numeric text-ink hover:underline"
                >
                  {stripSuffix(item.symbol)}
                </button>
                <span className="ml-2 hidden text-xs text-faint lg:inline">
                  {item.name}
                </span>
              </th>
              <td className="numeric px-4 py-2.5 text-right text-muted">
                {formatInr(item.quote.price)}
              </td>
              <td
                className={`numeric px-4 py-2.5 text-right ${item.today_change_pct >= 0 ? "text-up" : "text-down"}`}
              >
                {formatSignedPercent(item.today_change_pct)}
              </td>
              <td className="numeric hidden px-4 py-2.5 text-right text-faint sm:table-cell">
                {formatSignedPercent(item.residual_pct)}
              </td>
              <td className="hidden px-4 py-2.5 md:table-cell">
                <FreshnessBadge quote={item.quote} />
              </td>
              <td className="px-4 py-2.5 text-right">
                <button
                  type="button"
                  onClick={() => onRemove(item.symbol)}
                  className="text-xs text-faint transition-colors hover:text-down"
                >
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
