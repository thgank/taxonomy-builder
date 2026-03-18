import Link from "next/link";

import type { Page } from "@/shared/lib/pagination";
import { Button } from "@/shared/ui/button";

export interface PaginationControlsProps {
  page: Page<unknown>;
  pathname: string;
  searchParams: Record<string, string | string[] | undefined>;
  pageParam: string;
  sizeParam?: string;
}

function toHref(
  pathname: string,
  searchParams: Record<string, string | string[] | undefined>,
  pageParam: string,
  nextPage: number,
) {
  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(searchParams)) {
    if (value === undefined) {
      continue;
    }

    if (Array.isArray(value)) {
      for (const item of value) {
        params.append(key, item);
      }
      continue;
    }

    params.set(key, value);
  }

  params.set(pageParam, String(nextPage));

  return `${pathname}?${params.toString()}`;
}

export function PaginationControls({
  page,
  pathname,
  searchParams,
  pageParam,
}: PaginationControlsProps) {
  if (page.totalPages <= 1) {
    return null;
  }

  return (
    <div className="mt-5 flex items-center justify-between gap-4">
      <p className="text-sm text-[color:var(--color-muted)]">
        Page {page.number + 1} of {page.totalPages}
      </p>
      <div className="flex gap-3">
        <Link
          aria-disabled={page.first}
          href={toHref(pathname, searchParams, pageParam, Math.max(page.number - 1, 0))}
          scroll={false}
          tabIndex={page.first ? -1 : undefined}
        >
          <Button disabled={page.first} variant="secondary">
            Previous
          </Button>
        </Link>
        <Link
          aria-disabled={page.last}
          href={toHref(
            pathname,
            searchParams,
            pageParam,
            Math.min(page.number + 1, Math.max(page.totalPages - 1, 0)),
          )}
          scroll={false}
          tabIndex={page.last ? -1 : undefined}
        >
          <Button disabled={page.last} variant="secondary">
            Next
          </Button>
        </Link>
      </div>
    </div>
  );
}
