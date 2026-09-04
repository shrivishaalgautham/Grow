import type { HistoryOut } from "@/api/types";

const WIDTH = 560;
const HEIGHT = 140;
const PAD = 4;

function toPath(values: (number | null)[], min: number, span: number) {
  const step = (WIDTH - PAD * 2) / Math.max(1, values.length - 1);
  const segments: string[] = [];
  let open = false;

  values.forEach((value, index) => {
    if (value === null) {
      open = false;
      return;
    }
    const x = PAD + index * step;
    const y = HEIGHT - PAD - ((value - min) / span) * (HEIGHT - PAD * 2);
    segments.push(`${open ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`);
    open = true;
  });

  return segments.join(" ");
}

export function Sparkline({ history }: { history: HistoryOut }) {
  const closes = history.bars.map((bar) => bar.close);
  if (closes.length < 2) return null;

  const sma20 = history.sma["20"];
  const pool = [...closes, ...sma20.filter((v): v is number => v !== null)];
  const min = Math.min(...pool);
  const max = Math.max(...pool);
  const span = max - min || 1;

  const line = toPath(closes, min, span);
  const rising = closes[closes.length - 1] >= closes[0];

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className="h-32 w-full"
      role="img"
      aria-label={`Closing price over the last ${closes.length} sessions, ${rising ? "up" : "down"} over the window`}
    >
      <path
        d={`${line} L${WIDTH - PAD} ${HEIGHT} L${PAD} ${HEIGHT} Z`}
        fill={rising ? "var(--color-up)" : "var(--color-down)"}
        fillOpacity="0.08"
      />
      <path
        d={toPath(sma20, min, span)}
        fill="none"
        stroke="var(--color-faint)"
        strokeWidth="1"
        strokeDasharray="3 3"
      />
      <path
        d={line}
        fill="none"
        stroke={rising ? "var(--color-up)" : "var(--color-down)"}
        strokeWidth="1.75"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
