import type { ReactNode } from "react";

export interface SectionHeadingProps {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  action,
}: SectionHeadingProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="space-y-2">
        {eyebrow ? (
          <p className="text-[11px] font-semibold uppercase tracking-[0.26em] text-[color:var(--color-accent)]">
            {eyebrow}
          </p>
        ) : null}
        <div className="space-y-1">
          <h2 className="text-[1.75rem] font-semibold tracking-[-0.05em] text-[color:var(--color-ink)]">
            {title}
          </h2>
          {description ? (
            <p className="max-w-2xl text-sm leading-6 text-[color:var(--color-muted)]">
              {description}
            </p>
          ) : null}
        </div>
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  );
}
