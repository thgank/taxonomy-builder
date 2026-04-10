"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { cn } from "@/shared/lib/cn";

interface AppShellProps {
  children: ReactNode;
}

interface NavItem {
  href: string;
  label: string;
  active: boolean;
  helper?: string;
}

function getPageMeta(pathname: string) {
  if (pathname.startsWith("/collections/")) {
    return {
      title: "Collection Workspace",
      subtitle: "Curate source material, launch fresh runs, and shape each taxonomy version.",
      routeLabel: "Collection",
    };
  }

  if (pathname.startsWith("/jobs/")) {
    return {
      title: "Job Monitor",
      subtitle: "Track progress, review milestones, and keep long-running work on schedule.",
      routeLabel: "Run",
    };
  }

  if (pathname.startsWith("/documents/")) {
    return {
      title: "Document Payload",
      subtitle: "Review file details and the text segments prepared for taxonomy work.",
      routeLabel: "Document",
    };
  }

  if (pathname.startsWith("/taxonomies/")) {
    return {
      title: "Taxonomy Explorer",
      subtitle: "Explore branches, refine relationships, and inspect concept evidence.",
      routeLabel: "Taxonomy",
    };
  }

  return {
    title: "Collections",
    subtitle: "Organize knowledge spaces for each dataset, team, or domain.",
    routeLabel: "Overview",
  };
}

function getContextItems(pathname: string): NavItem[] {
  const items: NavItem[] = [
    {
      href: "/collections",
      label: "Collections",
      active: pathname === "/collections" || pathname === "/",
      helper: "All spaces",
    },
  ];

  if (pathname.startsWith("/collections/")) {
    items.push({
      href: pathname,
      label: "Current collection",
      active: true,
      helper: "Open workspace",
    });
  }

  if (pathname.startsWith("/jobs/")) {
    items.push({ href: pathname, label: "Current run", active: true, helper: "View progress" });
  }

  if (pathname.startsWith("/documents/")) {
    items.push({
      href: pathname,
      label: "Current document",
      active: true,
      helper: "Open file",
    });
  }

  if (pathname.startsWith("/taxonomies/")) {
    items.push({
      href: pathname,
      label: "Current taxonomy",
      active: true,
      helper: "Open structure",
    });
  }

  return items;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const pageMeta = getPageMeta(pathname);
  const navItems = getContextItems(pathname);
  const todayLabel = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date());

  return (
    <div className="mx-auto min-h-screen w-full max-w-[1600px] px-4 py-4 lg:px-6">
      <div className="grid min-h-[calc(100vh-2rem)] gap-4 lg:grid-cols-[272px_minmax(0,1fr)]">
        <aside className="dashboard-panel hidden min-h-full flex-col justify-between overflow-hidden px-5 py-6 lg:flex">
          <div className="space-y-8">
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-[color:var(--color-border-strong)] bg-[color:var(--color-ink)] text-sm font-semibold tracking-[0.18em] text-white">
                  TX
                </div>
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[color:var(--color-accent)]">
                    Taxonomy Studio
                  </p>
                  <p className="mt-1 text-lg font-semibold tracking-[-0.03em] text-[color:var(--color-ink)]">
                    Workspace
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[color:var(--color-muted-soft)]">
                Navigation
              </p>
              <nav className="space-y-2">
                {navItems.map((item) => (
                  <Link
                    className={cn(
                      "flex items-center justify-between gap-3 rounded-2xl border px-4 py-3 text-sm transition",
                      item.active
                        ? "border-[color:var(--color-border-strong)] bg-[color:var(--color-surface-muted)] text-[color:var(--color-ink)]"
                        : "border-transparent text-[color:var(--color-muted)] hover:border-[color:var(--color-border)] hover:bg-white/60 hover:text-[color:var(--color-ink)]",
                    )}
                    href={item.href}
                    key={`${item.href}-${item.label}`}
                  >
                    <div>
                      <p className="font-medium">{item.label}</p>
                      {item.helper ? (
                        <p className="mt-1 text-[11px] text-[color:var(--color-muted-soft)]">
                          {item.helper}
                        </p>
                      ) : null}
                    </div>
                    <span className="text-[10px] uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
                      open
                    </span>
                  </Link>
                ))}
              </nav>
            </div>
          </div>

          <div className="rounded-[24px] border border-[color:var(--color-border)] bg-[color:var(--color-surface-muted)] p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[color:var(--color-muted-soft)]">
              Today
            </p>
            <p className="mt-2 text-sm font-semibold text-[color:var(--color-ink)]">{todayLabel}</p>
            <p className="mt-1 text-sm text-[color:var(--color-muted)]">{pageMeta.routeLabel}</p>
          </div>
        </aside>

        <div className="min-w-0 space-y-4">
          <header className="dashboard-panel px-4 py-4 sm:px-6">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-[color:var(--color-muted-soft)]">
                  <span>{pageMeta.routeLabel}</span>
                  <span className="h-1 w-1 rounded-full bg-[color:var(--color-muted-soft)]" />
                  <span>Taxonomy Studio</span>
                </div>
                <div>
                  <h1 className="text-2xl font-semibold tracking-[-0.05em] text-[color:var(--color-ink)] sm:text-[2rem]">
                    {pageMeta.title}
                  </h1>
                  <p className="mt-1 max-w-3xl text-sm leading-6 text-[color:var(--color-muted)]">
                    {pageMeta.subtitle}
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <div className="flex min-w-[240px] items-center rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-muted)] px-4 py-3 text-sm text-[color:var(--color-muted)]">
                  Search collections, documents, or taxonomy concepts
                </div>
                <div className="flex items-center gap-3">
                  <div className="inline-flex items-center rounded-2xl border border-[color:var(--color-border)] bg-white/80 px-4 py-3 text-sm font-medium text-[color:var(--color-ink)]">
                    {todayLabel}
                  </div>
                  <Link
                    className="inline-flex items-center rounded-2xl border border-[color:var(--color-ink)] bg-[color:var(--color-ink)] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[color:var(--color-ink-soft)]"
                    href="/collections"
                  >
                    Collections
                  </Link>
                </div>
              </div>
            </div>
          </header>

          <main className="min-w-0">{children}</main>
        </div>
      </div>
    </div>
  );
}
