import { formatSignedPercent } from "@/lib/format";

const tone = (value: number) =>
  value > 0 ? "text-up" : value < 0 ? "text-down" : "text-muted";

function Column({
  label,
  value,
  hint,
  emphasis,
}: {
  label: string;
  value: number;
  hint: string;
  emphasis?: boolean;
}) {
  return (
    <div className="min-w-0">
      <p className="text-[11px] font-medium tracking-wide text-faint uppercase">
        {label}
      </p>
      <p
        className={`numeric mt-1 ${emphasis ? "text-xl" : "text-lg"} ${tone(value)}`}
      >
        {formatSignedPercent(value)}
      </p>
      <p className="mt-0.5 text-[11px] leading-tight text-faint">{hint}</p>
    </div>
  );
}

export function Decomposition({
  today,
  peer,
  residual,
  peerHint = "Its group did this too",
}: {
  today: number;
  peer: number;
  residual: number;
  peerHint?: string;
}) {
  const magnitude = Math.abs(peer) + Math.abs(residual);
  const peerShare = magnitude === 0 ? 0 : (Math.abs(peer) / magnitude) * 100;

  return (
    <div>
      <div className="grid grid-cols-3 gap-4">
        <Column label="Today" value={today} hint="Total price move" />
        <Column label="Peers" value={peer} hint={peerHint} />
        <Column
          label="Stock-specific"
          value={residual}
          hint="Left unexplained"
          emphasis
        />
      </div>

      <div
        className="mt-3 flex h-1.5 overflow-hidden rounded-full bg-line"
        role="img"
        aria-label={`${Math.round(peerShare)} percent of the move came from its peer group, ${Math.round(100 - peerShare)} percent is stock-specific`}
      >
        <div className="bg-faint" style={{ width: `${peerShare}%` }} />
        <div
          className={residual >= 0 ? "bg-up" : "bg-down"}
          style={{ width: `${100 - peerShare}%` }}
        />
      </div>
      <p className="mt-1.5 text-[11px] text-faint">
        {Math.round(100 - peerShare)}% of the move is this stock, not its group
      </p>
    </div>
  );
}
