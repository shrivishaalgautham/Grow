"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

function NavLink({ href, children }: { href: string; children: ReactNode }) {
  const pathname = usePathname();
  const isActive = pathname === href;

  return (
    <Link
      href={href}
      aria-current={isActive ? "page" : undefined}
      className={`rounded-md px-2.5 py-1.5 text-[13px] transition-colors ${
        isActive ? "bg-brand-soft text-brand-strong" : "text-muted hover:text-ink"
      }`}
    >
      {children}
    </Link>
  );
}

export function AppHeader({ actions }: { actions?: ReactNode }) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-canvas/90 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-1">
          <Link
            href="/watchlist"
            className="mr-2 flex shrink-0 items-center gap-2 text-[13px] font-semibold tracking-tight text-ink"
          >
            <span
              className="flex h-6 w-6 items-center justify-center rounded-md bg-brand text-[13px] font-bold text-white"
              aria-hidden
            >
              W
            </span>
            <span className="hidden sm:inline">Smart Market Watchlist</span>
            <span className="sm:hidden">Watchlist</span>
          </Link>
          <nav className="flex items-center gap-0.5">
            <NavLink href="/watchlist">Digest</NavLink>
            <NavLink href="/evidence">Evidence</NavLink>
          </nav>
        </div>
        {actions}
      </div>
    </header>
  );
}
