import type { ReactNode } from "react";

const TONES = {
  neutral: "border-line bg-raised text-muted",
  warn: "border-delayed/35 bg-delayed/[0.07] text-delayed",
  info: "border-notable/35 bg-notable/[0.07] text-notable",
} as const;

export function StateBanner({
  tone = "neutral",
  title,
  children,
  action,
}: {
  tone?: keyof typeof TONES;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div
      role="status"
      className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border px-4 py-3 text-sm ${TONES[tone]}`}
    >
      <div className="min-w-0">
        <p className="font-medium">{title}</p>
        {children && (
          <p className="mt-0.5 text-[13px] text-muted">{children}</p>
        )}
      </div>
      {action}
    </div>
  );
}
