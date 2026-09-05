import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import localFont from "next/font/local";
import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const jakarta = Plus_Jakarta_Sans({ variable: "--font-jakarta", subsets: ["latin"] });
const symbols = localFont({
  src: "../fonts/material-symbols-subset.woff2",
  variable: "--font-symbols",
  display: "block",
  weight: "100 700",
});

export const metadata: Metadata = {
  title: "Smart Market Watchlist",
  description:
    "What changed since you last looked, and whether it is the stock or the market.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${jakarta.variable} ${symbols.variable} h-full`}>
      <body className="min-h-full flex flex-col bg-surface text-body-md text-on-surface">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
