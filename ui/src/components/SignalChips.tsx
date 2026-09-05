import type { CatalystStatus, Signal, SignalType } from "@/api/types";
import { Icon } from "./Icon";
import type { IconName } from "./icons";

const CHIP: Record<SignalType, { icon: IconName; classes: string }> = {
  EXCESS_MOVE: { icon: "trending_up", classes: "bg-primary/10 text-primary" },
  VOLUME_CONFIRMED: { icon: "bar_chart", classes: "bg-primary/10 text-primary" },
  LEVEL_BREAK: { icon: "show_chart", classes: "bg-secondary-container text-on-secondary-fixed" },
  SINCE_SEEN_MOVE: { icon: "history", classes: "bg-surface-container-high text-on-surface" },
  USER_RULE: { icon: "rule", classes: "bg-primary-container/20 text-on-primary-container" },
  GAP: { icon: "arrow_outward", classes: "bg-tertiary-fixed/30 text-tertiary" },
  SMA_CROSSOVER: { icon: "auto_graph", classes: "bg-secondary-container text-on-secondary-fixed" },
  RSI_EXTREME: { icon: "query_stats", classes: "bg-surface-container-high text-on-surface" },
};

export const SIGNAL_NAMES: Record<SignalType, string> = {
  EXCESS_MOVE: "Excess move",
  VOLUME_CONFIRMED: "Volume confirmed",
  LEVEL_BREAK: "Level break",
  SINCE_SEEN_MOVE: "Since you looked",
  USER_RULE: "Your rule",
  GAP: "Gap",
  SMA_CROSSOVER: "SMA crossover",
  RSI_EXTREME: "RSI extreme",
};

export function SignalChip({ signal }: { signal: Signal }) {
  const chip = CHIP[signal.type];
  return (
    <div
      title={signal.detail}
      className={`inline-flex items-center gap-space-xs px-space-md py-space-2xs rounded-full font-label-sm text-label-sm font-semibold ${chip.classes}`}
    >
      <Icon name={chip.icon} size={15} />
      <span>{signal.type}</span>
      <span className="text-on-surface-variant font-normal hidden sm:inline">• {signal.headline}</span>
    </div>
  );
}

const CATALYST_CHIP: Partial<Record<CatalystStatus, { icon: IconName; classes: string; text: string }>> = {
  found: { icon: "feed", classes: "bg-surface-container-high text-on-surface", text: "Catalyst found" },
  none_found: { icon: "search_off", classes: "bg-tertiary-fixed/40 text-on-tertiary-fixed", text: "No public catalyst found" },
  pending: { icon: "progress_activity", classes: "bg-surface-container text-secondary", text: "Looking for a catalyst…" },
  unavailable: { icon: "cloud_off", classes: "bg-surface-container text-secondary", text: "Catalyst source unavailable" },
};

export function CatalystChip({ status, headline }: { status: CatalystStatus; headline?: string }) {
  const chip = CATALYST_CHIP[status];
  if (!chip) return null;
  return (
    <div className={`inline-flex items-center gap-space-xs px-space-md py-space-2xs rounded-full font-label-sm text-label-sm font-bold ${chip.classes}`}>
      <Icon name={chip.icon} size={15} className={status === "none_found" ? "text-tertiary" : "text-primary"} />
      <span className="truncate max-w-[36ch]">{status === "found" && headline ? `Catalyst found: ${headline}` : chip.text}</span>
    </div>
  );
}
