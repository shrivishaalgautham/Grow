export function SiteFooter() {
  return (
    <footer className="w-full bg-surface-container-lowest mt-auto shadow-[0_-1px_8px_rgba(0,0,0,0.02)]">
      <div className="max-w-7xl mx-auto px-margin-mobile md:px-margin-tablet lg:px-margin-desktop py-space-xl flex flex-col md:flex-row items-center justify-between gap-space-md font-body-sm text-body-sm text-on-surface-variant">
        <span>Smart Market Watchlist. An attention-allocation tool, not advice.</span>
        <div className="flex items-center gap-space-xl font-label-sm text-label-sm">
          <span>Quotes: Yahoo, cross-checked with BSE</span>
          <span>Announcements: NSE</span>
          <span>Never validated against outcomes</span>
        </div>
      </div>
    </footer>
  );
}
