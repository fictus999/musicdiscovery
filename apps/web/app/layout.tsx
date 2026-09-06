import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Music Discovery",
  description: "Find music by what makes it feel the way it does.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="top-nav">
          <div className="container">
            <Link href="/" className="brand">
              Music Discovery
            </Link>
          </div>
        </div>
        {children}
      </body>
    </html>
  );
}
