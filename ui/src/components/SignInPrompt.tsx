"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSession } from "@/hooks/useSession";
import { Icon } from "./Icon";

export function useSignInPrompt() {
  const [blockedAction, setBlockedAction] = useState<string | null>(null);
  const requireSignIn = useCallback(
    (action: string) => () => setBlockedAction(action),
    [],
  );
  const dismiss = useCallback(() => setBlockedAction(null), []);
  return { blockedAction, requireSignIn, dismiss };
}

export function SignInPrompt({
  action,
  onDismiss,
}: {
  action: string;
  onDismiss: () => void;
}) {
  const { signInWithGoogle } = useSession();
  const primaryRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const restoreTo = document.activeElement as HTMLElement | null;
    primaryRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      // Capture phase runs before DetailDrawer's own document listener, which would otherwise close it too.
      event.stopImmediatePropagation();
      onDismiss();
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      restoreTo?.focus();
    };
  }, [onDismiss]);

  return (
    <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center p-margin-mobile">
      <button
        type="button"
        aria-label="Dismiss sign-in prompt"
        onClick={onDismiss}
        className="absolute inset-0 bg-on-surface/30 backdrop-blur-[3px]"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="sign-in-prompt-title"
        className="relative w-full max-w-md bg-surface-container-lowest rounded-xl shadow-2xl p-space-xl space-y-space-lg"
      >
        <div className="space-y-space-xs">
          <div className="flex items-center gap-space-xs text-primary font-label-sm text-label-sm uppercase tracking-wider font-bold">
            <Icon name="visibility" size={18} />
            <span>Demo is read-only</span>
          </div>
          <h2 id="sign-in-prompt-title" className="font-headline-md text-headline-md text-on-surface">
            Sign in to {action}
          </h2>
          <p className="font-body-md text-body-md text-on-surface-variant">
            You are looking at a sample watchlist that everyone shares, so nothing here can be
            changed. Take a watchlist of your own and this works immediately.
          </p>
        </div>

        <div className="space-y-space-sm">
          <button
            ref={primaryRef}
            type="button"
            onClick={() => {
              signInWithGoogle();
              onDismiss();
            }}
            className="w-full flex items-center justify-center gap-space-sm px-space-lg py-space-md bg-primary-container text-on-primary-fixed rounded-lg font-label-lg text-label-lg font-bold shadow-sm hover:opacity-95 transition-opacity"
          >
            <Icon name="verified" size={20} />
            Continue with Google
          </button>
          <Link
            href="/#start"
            className="w-full flex items-center justify-center gap-space-xs px-space-lg py-space-md bg-surface-container-low hover:bg-surface-container text-on-surface rounded-lg font-label-lg text-label-lg font-semibold transition-colors"
          >
            Start without an account
            <Icon name="arrow_forward" size={18} />
          </Link>
          <button
            type="button"
            onClick={onDismiss}
            className="w-full py-space-sm font-label-md text-label-md text-secondary hover:text-on-surface transition-colors"
          >
            Keep looking around
          </button>
        </div>
      </div>
    </div>
  );
}
