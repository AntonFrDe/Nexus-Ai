import type { Metadata } from "next";

import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "dockview-react/dist/styles/dockview.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "NEXUS",
  description: "Local AI orchestration studio",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark" data-accent="amber" data-density="compact">
      <body>{children}</body>
    </html>
  );
}
