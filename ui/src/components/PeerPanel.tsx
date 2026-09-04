"use client";

import { usePeers } from "@/hooks/usePeers";
import { formatSignedPercent, stripSuffix } from "@/lib/format";

export function PeerPanel({ symbol }: { symbol: string }) {
  const { data, isPending, isError } = usePeers(symbol);

  if (isPending) {
    return <div className="skeleton h-24 rounded-lg" aria-hidden />;
  }
  if (isError || !data) {
    return (
      <p className="text-[13px] text-faint">
        Peer group could not be loaded for this symbol.
      </p>
    );
  }

  const spread = Math.max(
    1,
    ...data.members.map((m) => Math.abs(m.today_change_pct)),
  );

  return (
    <div>
      <p className="text-[13px] text-muted">
        {data.method === "cluster"
          ? `Grouped by 90-day return behaviour, not by sector label. ${data.size} names move together.`
          : `No stable behavioural cluster, so the peer return is a beta-adjusted market return.`}{" "}
        The group moved{" "}
        <span
          className={`numeric ${data.peer_change_pct >= 0 ? "text-up" : "text-down"}`}
        >
          {formatSignedPercent(data.peer_change_pct)}
        </span>{" "}
        today.
      </p>

      <ul className="mt-3 space-y-1.5">
        {data.members.map((member) => {
          const width = (Math.abs(member.today_change_pct) / spread) * 50;
          const isSelf = member.symbol === symbol;
          return (
            <li key={member.symbol} className="flex items-center gap-3 text-xs">
              <span
                className={`numeric w-20 shrink-0 ${isSelf ? "text-ink" : "text-muted"}`}
              >
                {stripSuffix(member.symbol)}
              </span>
              <span className="relative flex h-3 flex-1 items-center">
                <span className="absolute inset-y-0 left-1/2 w-px bg-line" />
                <span
                  className={`absolute h-1.5 rounded-sm ${member.today_change_pct >= 0 ? "bg-up" : "bg-down"} ${isSelf ? "" : "opacity-45"}`}
                  style={{
                    width: `${width}%`,
                    left: member.today_change_pct >= 0 ? "50%" : `${50 - width}%`,
                  }}
                />
              </span>
              <span
                className={`numeric w-16 shrink-0 text-right ${member.today_change_pct >= 0 ? "text-up" : "text-down"} ${isSelf ? "" : "opacity-70"}`}
              >
                {formatSignedPercent(member.today_change_pct)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
