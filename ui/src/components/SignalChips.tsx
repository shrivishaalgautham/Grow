import type { Signal, SignalType } from "@/api/types";

const TONES: Record<SignalType, string> = {
  EXCESS_MOVE: "border-high/40 bg-high/10 text-high",
  VOLUME_CONFIRMED: "border-notable/40 bg-notable/10 text-notable",
  LEVEL_BREAK: "border-line-strong bg-raised text-ink",
  SINCE_SEEN_MOVE: "border-line-strong bg-raised text-muted",
  USER_RULE: "border-rule/40 bg-rule/10 text-rule",
};

const DOTS: Record<SignalType, string> = {
  EXCESS_MOVE: "bg-high",
  VOLUME_CONFIRMED: "bg-notable",
  LEVEL_BREAK: "bg-ink",
  SINCE_SEEN_MOVE: "bg-faint",
  USER_RULE: "bg-rule",
};

const NAMES: Record<SignalType, string> = {
  EXCESS_MOVE: "Excess move",
  VOLUME_CONFIRMED: "Volume confirmed",
  LEVEL_BREAK: "Level break",
  SINCE_SEEN_MOVE: "Since you looked",
  USER_RULE: "Your rule",
};

export function SignalChips({ signals }: { signals: Signal[] }) {
  if (signals.length === 0) return null;

  return (
    <ul className="flex flex-wrap gap-1.5">
      {signals.map((signal) => (
        <li key={`${signal.type}-${signal.fired_at}`}>
          <span
            className={`inline-block rounded border px-2 py-0.5 text-[11px] font-medium ${TONES[signal.type]}`}
            title={signal.detail}
          >
            {NAMES[signal.type]}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function SignalList({ signals }: { signals: Signal[] }) {
  return (
    <ul className="space-y-2.5">
      {signals.map((signal) => (
        <li key={`${signal.type}-${signal.fired_at}`} className="flex gap-3">
          <span
            className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${DOTS[signal.type]}`}
            aria-hidden
          />
          <div className="min-w-0">
            <p className="text-sm font-medium text-ink">{signal.headline}</p>
            <p className="mt-0.5 text-[13px] leading-relaxed text-muted">
              {signal.detail}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}
