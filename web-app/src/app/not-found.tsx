import Link from "next/link";

import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Card className="max-w-xl bg-[color:var(--color-surface-muted)] text-center">
        <p className="text-[11px] font-semibold uppercase tracking-[0.26em] text-[color:var(--color-accent)]">
          Resource Missing
        </p>
        <h1 className="mt-3 text-[2rem] font-semibold tracking-[-0.05em] text-[color:var(--color-ink)]">
          The requested record was not found.
        </h1>
        <p className="mt-3 text-sm leading-6 text-[color:var(--color-muted)]">
          Check the link or head back to your collections to keep working.
        </p>
        <div className="mt-6">
          <Link href="/collections">
            <Button>Open collections</Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}
