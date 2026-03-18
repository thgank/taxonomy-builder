import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/widgets/app-shell/app-shell";

import "./globals.css";

export const metadata: Metadata = {
  title: "Taxonomy Control Room",
  description: "Operational frontend for collections, jobs, taxonomies, and releases.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
