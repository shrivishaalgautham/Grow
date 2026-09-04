"use client";

import { useEffect, useRef, useState } from "react";
import { QRCodeSVG } from "qrcode.react";

export function ResumeLink({
  token,
  onClose,
}: {
  token: string;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  const url = `${window.location.origin}/?t=${token}`;

  useEffect(() => {
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  async function copy() {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2_000);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-black/70"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="resume-title"
        className="relative w-full max-w-sm rounded-xl border border-line bg-surface p-6"
      >
        <h2 id="resume-title" className="text-base font-semibold text-ink">
          Open this watchlist on your phone
        </h2>
        <p className="mt-1.5 text-[13px] leading-relaxed text-muted">
          Scan the code or copy the link. Anyone holding it has full access to
          this watchlist — there is no password.
        </p>

        <div className="mt-5 flex justify-center rounded-lg bg-white p-4">
          <QRCodeSVG value={url} size={168} level="M" marginSize={0} />
        </div>

        <p className="numeric mt-4 truncate rounded-md border border-line bg-raised px-3 py-2 text-[11px] text-faint">
          {url}
        </p>

        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={copy}
            className="flex-1 rounded-md bg-brand px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-brand-strong"
          >
            {copied ? "Copied" : "Copy link"}
          </button>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded-md border border-line px-3 py-2 text-xs font-medium text-muted transition-colors hover:border-line-strong hover:text-ink"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
