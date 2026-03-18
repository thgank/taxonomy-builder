"use client";

import { useEffect } from "react";

import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body>
        <div className="mx-auto flex min-h-screen max-w-7xl items-center justify-center px-5">
          <Card className="max-w-xl bg-[color:var(--color-surface-muted)] text-center">
            <p className="text-[11px] font-semibold uppercase tracking-[0.26em] text-[color:var(--color-accent)]">
              Unexpected Error
            </p>
            <h1 className="mt-3 text-[2rem] font-semibold tracking-[-0.05em] text-[color:var(--color-ink)]">
              The frontend could not complete that request.
            </h1>
            <p className="mt-3 text-sm leading-6 text-[color:var(--color-muted)]">
              Something interrupted the flow. Try again in a moment.
            </p>
            <div className="mt-6">
              <Button onClick={reset}>Try again</Button>
            </div>
          </Card>
        </div>
      </body>
    </html>
  );
}
