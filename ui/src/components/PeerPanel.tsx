"use client";

import { usePeers } from "@/hooks/usePeers";
import { formatSignedPercent, stripSuffix } from "@/lib/format";

export function PeerPanel({ symbol }: { symbol: string }) {
  const { data, isPending, isError } = usePeers(symbol);

  if (isPending) return <div className="skeleton h-32" aria-hidden />;
  if (isError || !data) return <p className="font-body-sm text-body-sm text-secondary">Peer group could not be loaded for this symbol.</p>;

  const members = data.members;
  const spread = Math.max(0.01, ...members.map((m) => Math.abs(m.today_change_pct)));

  return (
    <div>
      <div className="mb-space-md">
        <div className="flex items-center justify-between">
          <span className="font-headline-sm text-headline-sm text-on-surface">Peer group context</span>
          <span className="font-label-sm text-label-sm text-secondary">Group median: {formatSignedPercent(data.peer_change_pct)}</span>
        </div>
        <p className="font-body-sm text-body-sm text-on-surface-variant mt-space-2xs">
          {data.method === "cluster"
            ? `These ${data.size} stocks have moved together over the past year (behavioural cluster, not a sector label); today the group moved ${formatSignedPercent(data.peer_change_pct)}.`
            : `No stable behavioural cluster for this name, so the peer return is a beta-adjusted Nifty move of ${formatSignedPercent(data.peer_change_pct)}.`}
        </p>
      </div>
      {members.length === 0 ? (
        <p className="font-body-sm text-body-sm text-secondary">No cluster members to compare against.</p>
      ) : (
        <div className="space-y-space-sm font-label-md text-label-md">
          {members.map((member) => {
            const isSelf = member.symbol === symbol;
            const isUp = member.today_change_pct >= 0;
            const width = (Math.abs(member.today_change_pct) / spread) * 100;
            return (
              <div key={member.symbol} className={isSelf ? "p-space-sm rounded-lg bg-primary/5" : ""}>
                <div className={`flex items-center justify-between mb-space-2xs ${isSelf ? "font-bold text-on-surface" : "text-secondary"}`}>
                  <div className="flex items-center gap-space-xs">
                    {isSelf && <span className="w-1.5 h-1.5 rounded-full bg-primary" />}
                    <span>{stripSuffix(member.symbol)}</span>
                    {isSelf && <span className="font-label-sm text-label-sm text-primary font-normal">(this stock)</span>}
                  </div>
                  <span className={`font-metric-tabular tabular ${isUp ? "text-primary" : "text-error"} ${isSelf ? "font-bold" : ""}`}>
                    {formatSignedPercent(member.today_change_pct)}
                  </span>
                </div>
                <div className={`w-full h-1.5 rounded-full overflow-hidden ${isSelf ? "bg-surface-container-high h-2" : "bg-surface-container-low"}`}>
                  <div className={`h-full rounded-full ${isUp ? "bg-primary" : "bg-error"} ${isSelf ? "" : "opacity-55"}`} style={{ width: `${Math.max(2, width)}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
