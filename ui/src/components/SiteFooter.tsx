import Link from "next/link";
import { Icon } from "./Icon";

const PRODUCT_LINKS = [
  { href: "/watchlist", label: "Watchlist" },
  { href: "/evidence", label: "Evidence" },
];

const METHOD_FACTS = [
  "Quotes: Yahoo, cross-checked with BSE",
  "Announcements: NSE",
  "Never validated against outcomes",
];

export function SiteFooter() {
  return (
    <footer className="w-full bg-surface-container-lowest mt-auto shadow-[0_-1px_8px_rgba(0,0,0,0.02)]">
      <div className="max-w-7xl mx-auto px-margin-mobile md:px-margin-tablet lg:px-margin-desktop py-space-2xl grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-space-xl">
        <div className="space-y-space-sm lg:col-span-2">
          <Link href="/" className="inline-flex items-center gap-space-sm">
            <span className="w-8 h-8 rounded-lg bg-primary-container flex items-center justify-center text-on-primary-fixed">
              <Icon name="candlestick_chart" size={18} />
            </span>
            <span className="font-headline-sm text-headline-sm text-on-surface">Smart Market Watchlist</span>
          </Link>
          <p className="font-body-sm text-body-sm text-on-surface-variant max-w-sm">
            An attention-allocation tool, not advice. It decomposes a move against a stock&rsquo;s peers so you can
            tell what is specific to it from what the whole market did.
          </p>
        </div>

        <div className="space-y-space-sm">
          <span className="font-label-sm text-label-sm text-outline uppercase tracking-wider">Product</span>
          <ul className="space-y-space-xs">
            {PRODUCT_LINKS.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors"
                >
                  {link.label}
                </Link>
              </li>
            ))}
            <li>
              <a
                href="https://github.com/KaviyaaPriyadharshini/Groww-Hackathon"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-space-2xs font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors"
              >
                Source
                <Icon name="open_in_new" size={12} />
              </a>
            </li>
          </ul>
        </div>

        <div className="space-y-space-sm">
          <span className="font-label-sm text-label-sm text-outline uppercase tracking-wider">Methodology</span>
          <ul className="space-y-space-xs">
            {METHOD_FACTS.map((fact) => (
              <li key={fact} className="font-body-sm text-body-sm text-on-surface-variant">
                {fact}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="border-t border-surface-container">
        <div className="max-w-7xl mx-auto px-margin-mobile md:px-margin-tablet lg:px-margin-desktop py-space-md flex flex-col sm:flex-row items-center justify-between gap-space-sm font-label-sm text-label-sm text-outline">
          <span>&copy; {new Date().getFullYear()} Smart Market Watchlist</span>
          <span>No passwords. No advice. No outcome guarantees.</span>
        </div>
      </div>
    </footer>
  );
}
