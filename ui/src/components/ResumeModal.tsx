"use client";

import { useEffect, useRef, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { formatDay } from "@/lib/format";
import { Icon } from "./Icon";

export function ResumeModal({
  token,
  expiresAt,
  onClose,
}: {
  token: string;
  expiresAt: string | null;
  onClose: () => void;
}) {
  const [isCopied, setIsCopied] = useState(false);
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
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2_000);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-margin-mobile">
      <button type="button" aria-label="Close" onClick={onClose} className="absolute inset-0 bg-on-surface/30 backdrop-blur-[3px]" />
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="resume-title"
        className="relative w-full max-w-3xl bg-surface-container-lowest rounded-xl p-space-xl md:p-space-2xl shadow-2xl border border-secondary-container/40 space-y-space-md"
      >
        <div className="flex items-center justify-between border-b border-surface-container pb-space-sm">
          <div className="flex items-center gap-space-sm">
            <Icon name="devices" size={24} className="text-primary" />
            <h3 id="resume-title" className="font-headline-sm text-headline-sm text-on-surface">
              Resume session on mobile
            </h3>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="font-label-sm text-label-sm text-secondary bg-surface-container px-space-sm py-space-2xs rounded hover:text-on-surface"
          >
            Close
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-space-xl items-center pt-space-xs">
          <div className="flex flex-col items-center justify-center p-space-lg bg-surface-container-low rounded-xl text-center space-y-space-sm">
            <div className="bg-white p-2 rounded-lg shadow-sm">
              <QRCodeSVG value={url} size={144} level="M" marginSize={0} fgColor="#0b1c30" />
            </div>
            <span className="font-label-sm text-label-sm text-secondary">Scan with the phone camera</span>
          </div>
          <div className="md:col-span-2 space-y-space-md">
            <div className="space-y-space-2xs">
              <h4 className="font-headline-sm text-headline-sm text-on-surface">One-time resume link</h4>
              <p className="font-body-sm text-body-sm text-on-surface-variant">
                Opening it stores the session token on that device and removes it from the address bar. The same
                watchlist, seen-state, and rules follow you.
              </p>
            </div>
            <div className="flex items-center gap-space-sm bg-surface-container-low p-space-sm rounded-lg">
              <input readOnly value={url} className="w-full bg-transparent font-mono text-body-sm text-on-surface outline-none" />
              <button
                type="button"
                onClick={copy}
                className="px-space-md py-space-xs bg-surface-container-highest hover:bg-surface-container text-on-surface font-label-md text-label-md rounded-lg shrink-0 transition-colors flex items-center gap-space-2xs"
              >
                <Icon name="content_copy" size={16} />
                <span>{isCopied ? "Copied" : "Copy link"}</span>
              </button>
            </div>
            <div className="p-space-sm bg-tertiary-fixed/30 rounded-lg flex items-center gap-space-sm">
              <Icon name="lock_clock" size={20} className="text-tertiary shrink-0" />
              <p className="font-body-sm text-body-sm text-on-surface">
                <strong>No password protects this.</strong> Anyone holding the link has full access to the watchlist
                {expiresAt ? ` until ${formatDay(expiresAt.slice(0, 10))}` : ""}. Do not share it publicly.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
