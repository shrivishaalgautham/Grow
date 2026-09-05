import type { Item } from "@/api/types";
import { formatInr, formatSignedPercent, stripSuffix } from "@/lib/format";

const tone = (value: number) => (value > 0 ? "text-primary" : value < 0 ? "text-tertiary" : "text-on-surface");

export function peerLabel(item: Pick<Item, "peer">) {
  return item.peer.method === "cluster" ? `Peers (${item.peer.size} behavioural peers)` : "Peers (beta to Nifty)";
}

export function peerHint(item: Pick<Item, "peer">) {
  return item.peer.method === "cluster" ? "Median move of the cluster" : "Beta-weighted index move";
}

export function stockSpecificShare(item: Pick<Item, "peer_change_pct" | "residual_pct">) {
  const magnitude = Math.abs(item.peer_change_pct) + Math.abs(item.residual_pct);
  return magnitude === 0 ? 0 : (Math.abs(item.residual_pct) / magnitude) * 100;
}

export function Decomposition({ item, showRange = false }: { item: Item; showRange?: boolean }) {
  const share = stockSpecificShare(item);
  const range = item.quote.day_high - item.quote.day_low;
  const position = range <= 0 ? 50 : ((item.quote.price - item.quote.day_low) / range) * 100;

  return (
    <div className="my-space-md p-space-md bg-surface-container-low rounded-xl">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-space-md text-center">
        <div className="p-space-sm bg-surface-container-lowest rounded-lg">
          <div className="font-label-sm text-label-sm text-secondary uppercase tracking-wider">Today&rsquo;s return</div>
          <div className={`font-headline-sm text-headline-sm font-bold mt-space-2xs tabular ${tone(item.today_change_pct)}`}>
            {formatSignedPercent(item.today_change_pct)}
          </div>
          <div className="font-body-sm text-body-sm text-secondary">Gross move vs previous close</div>
        </div>
        <div className="p-space-sm bg-surface-container-lowest rounded-lg">
          <div className="font-label-sm text-label-sm text-secondary uppercase tracking-wider">{peerLabel(item)}</div>
          <div className="font-headline-sm text-headline-sm text-on-surface font-bold mt-space-2xs tabular">
            {formatSignedPercent(item.peer_change_pct)}
          </div>
          <div className="font-body-sm text-body-sm text-secondary">{peerHint(item)}</div>
        </div>
        <div className="p-space-sm bg-surface-container-lowest rounded-lg">
          <div className={`font-label-sm text-label-sm uppercase tracking-wider font-bold ${tone(item.residual_pct)}`}>Stock-specific</div>
          <div className={`font-headline-sm text-headline-sm font-bold mt-space-2xs tabular ${tone(item.residual_pct)}`}>
            {formatSignedPercent(item.residual_pct)}
          </div>
          <div className="font-body-sm text-body-sm text-secondary">Left unexplained by peers</div>
        </div>
      </div>

      <div className="mt-space-md space-y-space-xs">
        <div className="flex items-center justify-between font-label-sm text-label-sm">
          <span className="text-secondary">Stock-specific share of the move</span>
          <span className={`font-bold ${tone(item.residual_pct)}`}>{Math.round(share)}% is this stock</span>
        </div>
        <div
          className="w-full h-2.5 bg-surface-container rounded-full overflow-hidden flex"
          role="img"
          aria-label={`${Math.round(100 - share)} percent of the move is peer or market, ${Math.round(share)} percent is stock-specific`}
        >
          <div className="h-full bg-secondary" style={{ width: `${100 - share}%` }} />
          <div className={`h-full ${item.residual_pct >= 0 ? "bg-primary-container" : "bg-tertiary"}`} style={{ width: `${share}%` }} />
        </div>
        <div className="flex items-center justify-between text-secondary font-label-sm text-label-sm pt-space-2xs">
          <span className="flex items-center gap-space-2xs"><span className="w-2 h-2 rounded-full bg-secondary inline-block" /> Market / peer component</span>
          <span className="flex items-center gap-space-2xs">
            <span className={`w-2 h-2 rounded-full inline-block ${item.residual_pct >= 0 ? "bg-primary-container" : "bg-tertiary"}`} /> {stripSuffix(item.symbol)} unique component
          </span>
        </div>
      </div>

      {showRange && (
        <div className="mt-space-md space-y-space-xs">
          <div className="flex items-center justify-between font-label-sm text-label-sm text-secondary">
            <span>Day low {formatInr(item.quote.day_low)}</span>
            <span>Day high {formatInr(item.quote.day_high)}</span>
          </div>
          <div className="relative w-full h-2 bg-surface-container rounded-full overflow-hidden">
            <div className={`absolute left-0 top-0 bottom-0 ${item.today_change_pct >= 0 ? "bg-primary-container" : "bg-tertiary"}`} style={{ width: `${Math.max(2, Math.min(100, position))}%` }} />
          </div>
        </div>
      )}
    </div>
  );
}
