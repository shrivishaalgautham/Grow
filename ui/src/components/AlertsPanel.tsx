"use client";

import { useState } from "react";
import { isRateLimited } from "@/api/errors";
import { useNotifications } from "@/hooks/useNotifications";
import { formatRelative, formatRetryAfter } from "@/lib/format";
import { Icon } from "./Icon";

const EMAIL_PATTERN = /^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$/;

export function AlertsPanel({
  enabled,
  onRequireSignIn,
}: {
  enabled: boolean;
  onRequireSignIn?: () => void;
}) {
  const [email, setEmail] = useState("");
  const { status, subscribe, remove } = useNotifications(enabled);
  const channel = status.data?.email ?? null;
  const isValid = EMAIL_PATTERN.test(email.trim());

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (onRequireSignIn) return onRequireSignIn();
    if (isValid) subscribe.mutate(email.trim(), { onSuccess: () => setEmail("") });
  }

  return (
    <section className="bg-surface-container-lowest rounded-xl p-space-xl md:p-space-2xl shadow-sm space-y-space-lg">
      <div className="flex items-center justify-between gap-space-md">
        <div className="space-y-space-2xs">
          <div className="flex items-center gap-space-xs text-primary font-label-sm text-label-sm uppercase tracking-wider font-bold">
            <Icon name="mail" size={18} />
            <span>Email alerts</span>
          </div>
          <h2 className="font-headline-md text-headline-md text-on-surface">Hear about it while you are away</h2>
          <p className="font-body-sm text-body-sm text-secondary">
            One email at most every 30 minutes, only when a watched stock does something its peers did not, or one of
            your rules matches. Never a buy or sell call. The address is stored only after you confirm it.
          </p>
        </div>
        {channel && (
          <span
            className={`px-space-sm py-space-2xs font-label-sm text-label-sm rounded-full font-bold shrink-0 ${
              channel.status === "verified"
                ? "bg-primary-container/20 text-on-primary-container"
                : channel.status === "pending"
                  ? "bg-secondary-container text-on-secondary-fixed"
                  : "bg-surface-container text-secondary"
            }`}
          >
            {channel.status === "verified" ? "Active" : channel.status === "pending" ? "Awaiting confirmation" : "Switched off"}
          </span>
        )}
      </div>

      {channel?.status === "verified" ? (
        <div className="p-space-md bg-surface-container-low rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-space-md">
          <div className="flex items-center gap-space-sm min-w-0">
            <Icon name="mark_email_read" size={20} className="text-primary" />
            <div className="min-w-0">
              <p className="font-label-md text-label-md text-on-surface">Alerts go to {channel.address_masked}</p>
              <p className="font-body-sm text-body-sm text-secondary">
                {channel.last_notified_at ? `Last email ${formatRelative(channel.last_notified_at)}` : "Nothing sent yet; the next qualifying signal triggers one."}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onRequireSignIn ?? (() => remove.mutate())}
            disabled={remove.isPending}
            className="px-space-md py-space-xs bg-surface-container hover:bg-error-container hover:text-on-error-container text-on-surface font-label-md text-label-md rounded-lg transition-colors disabled:opacity-60 shrink-0"
          >
            Turn off and forget the address
          </button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-space-sm">
          {channel?.status === "pending" && (
            <div className="p-space-sm bg-secondary-container/60 rounded-lg flex items-center gap-space-sm">
              <Icon name="schedule_send" size={18} className="text-primary" />
              <p className="font-body-sm text-body-sm text-on-secondary-fixed">
                A confirmation link was sent to {channel.address_masked}. Open it on any device to activate alerts. Entering an address again sends a fresh link.
              </p>
            </div>
          )}
          {channel?.status === "disabled" && (
            <p className="font-body-sm text-body-sm text-secondary">
              Alerts to {channel.address_masked} were switched off from an email link. Enter the address again to re-confirm.
            </p>
          )}
          <div className="flex flex-col sm:flex-row gap-space-sm">
            <input
              type="email"
              value={email}
              maxLength={254}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              aria-label="Email address for alerts"
              className="flex-1 px-space-md py-space-sm bg-surface-container-low text-on-surface rounded-lg font-body-md text-body-md outline-none ring-2 ring-primary/20 focus:ring-primary placeholder:text-secondary"
            />
            <button
              type="submit"
              disabled={subscribe.isPending || (!isValid && !onRequireSignIn)}
              className="px-space-xl py-space-sm bg-primary hover:bg-primary/90 text-on-primary font-label-lg text-label-lg rounded-lg shadow-sm transition-colors flex items-center justify-center gap-space-xs shrink-0 disabled:opacity-50"
            >
              <Icon name="send" size={18} />
              <span>{subscribe.isPending ? "Sending…" : "Send confirmation link"}</span>
            </button>
          </div>
          {isRateLimited(subscribe.error) && (
            <p role="alert" className="font-body-sm text-body-sm text-tertiary">
              Too many confirmation links. Try again in {formatRetryAfter(subscribe.error.retryAfterSeconds ?? 60)}.
            </p>
          )}
          {subscribe.error && !isRateLimited(subscribe.error) && (
            <p role="alert" className="font-body-sm text-body-sm text-tertiary">{subscribe.error.message}</p>
          )}
        </form>
      )}
    </section>
  );
}
