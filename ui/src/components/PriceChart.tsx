import type { HistoryOut, Levels } from "@/api/types";
import { formatDay, formatInr, formatSignedPercent } from "@/lib/format";

const WIDTH = 620;
const HEIGHT = 230;
const LEFT = 48;
const RIGHT = 600;
const TOP = 14;
const BOTTOM = 195;
const BAR_MAX = 100;

type Scale = (value: number) => number;

function linePath(values: (number | null)[], xAt: (i: number) => number, y: Scale) {
  let open = false;
  const parts: string[] = [];
  values.forEach((value, index) => {
    if (value === null) {
      open = false;
      return;
    }
    parts.push(`${open ? "L" : "M"}${xAt(index).toFixed(1)} ${y(value).toFixed(1)}`);
    open = true;
  });
  return parts.join(" ");
}

function LevelLine({ y, label, tone, dash }: { y: number; label: string; tone: string; dash: string }) {
  return (
    <g className={tone}>
      <line stroke="currentColor" strokeDasharray={dash} x1={LEFT} x2={RIGHT} y1={y} y2={y} />
      <text className="fill-current" fontSize="9.5" textAnchor="end" x={LEFT - 5} y={y + 3.5}>
        {label}
      </text>
    </g>
  );
}

export function PriceChart({ history, levels, price, todayChangePct }: { history: HistoryOut; levels: Levels; price: number; todayChangePct: number }) {
  const closes = history.bars.map((bar) => bar.close);
  if (closes.length < 2) return null;
  const sma20 = history.sma["20"];
  const sma50 = history.sma["50"];
  const inWindow = (level: number) => level >= Math.min(...closes) * 0.9 && level <= Math.max(...closes) * 1.1;
  const guides = [
    { value: levels.high_52w, label: `${formatInr(levels.high_52w)} (52W H)`, tone: "text-tertiary", dash: "3 3" },
    { value: levels.prev_high, label: `${formatInr(levels.prev_high)} (PDH)`, tone: "text-secondary", dash: "2 2" },
    { value: levels.low_52w, label: `${formatInr(levels.low_52w)} (52W L)`, tone: "text-secondary", dash: "0" },
  ].filter((guide) => inWindow(guide.value));
  const pool = [...closes, ...sma20.filter((v): v is number => v !== null), ...sma50.filter((v): v is number => v !== null), ...guides.map((g) => g.value)];
  const min = Math.min(...pool);
  const max = Math.max(...pool);
  const span = max - min || 1;
  const y: Scale = (value) => BOTTOM - ((value - min) / span) * (BOTTOM - TOP);
  const xAt = (index: number) => LEFT + (index / (closes.length - 1)) * (RIGHT - LEFT);
  const residuals = history.bars.map((bar) => bar.residual_pct);
  const residualMax = Math.max(0.01, ...residuals.map((r) => Math.abs(r)));
  const barWidth = Math.max(2, Math.min(6, (RIGHT - LEFT) / closes.length - 1));
  const lastX = xAt(closes.length - 1);
  const lastY = y(closes[closes.length - 1]);
  const first = history.bars[0].date;
  const mid = history.bars[Math.floor(history.bars.length / 2)].date;
  const isRising = closes[closes.length - 1] >= closes[0];

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full h-56 select-none overflow-visible" role="img" aria-label={`Closing price over ${closes.length} sessions with 20 and 50 day averages and daily stock-specific residual bars`}>
      <g className="opacity-40">
        {guides.map((guide) => (
          <LevelLine key={guide.label} y={y(guide.value)} label={guide.label} tone={guide.tone} dash={guide.dash} />
        ))}
      </g>
      <g>
        {residuals.map((residual, index) => {
          const height = (Math.abs(residual) / residualMax) * BAR_MAX;
          const isLast = index === residuals.length - 1;
          return (
            <rect
              key={history.bars[index].date}
              x={xAt(index) - barWidth / 2}
              y={BOTTOM - height}
              width={isLast ? barWidth + 2 : barWidth}
              height={height}
              rx={1}
              className={residual >= 0 ? "fill-primary-container" : "fill-tertiary-container"}
              opacity={isLast ? 1 : 0.55}
            />
          );
        })}
      </g>
      <path d={linePath(sma50, xAt, y)} fill="none" stroke="currentColor" className="text-secondary" strokeDasharray="3 3" strokeWidth="1.75" />
      <path d={linePath(sma20, xAt, y)} fill="none" stroke="currentColor" className="text-primary-fixed-dim" strokeDasharray="4 3" strokeWidth="2" />
      <path d={linePath(closes, xAt, y)} fill="none" stroke="currentColor" className={isRising ? "text-primary" : "text-tertiary"} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <circle className="fill-primary-container" cx={lastX} cy={lastY} r={5} />
      <circle className="fill-primary/20 animate-ping" cx={lastX} cy={lastY} r={9} />
      <g transform={`translate(${Math.min(lastX - 112, RIGHT - 118)}, ${Math.max(0, lastY - 44)})`}>
        <rect className="fill-inverse-surface" height="34" rx="6" width="118" x="0" y="0" />
        <text className="fill-inverse-on-surface" fontSize="9" fontWeight="600" x="8" y="14">LATEST SESSION</text>
        <text className="fill-primary-fixed" fontSize="10.5" fontWeight="700" x="8" y="27">
          {formatInr(price)} • {formatSignedPercent(todayChangePct)}
        </text>
      </g>
      <text className="fill-secondary" fontSize="9" x={LEFT} y="212">{formatDay(first)}</text>
      <text className="fill-secondary" fontSize="9" textAnchor="middle" x={(LEFT + RIGHT) / 2} y="212">{formatDay(mid)}</text>
      <text className="fill-primary" fontSize="9" fontWeight="600" textAnchor="end" x={RIGHT} y="212">Latest (NSE)</text>
    </svg>
  );
}
