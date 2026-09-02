// Shared loading placeholder for the table-shaped pages (Assets,
// Alerts, Audit Log). Exists because, before this component, those
// pages had no distinct loading state at all - an empty result and
// "still fetching" rendered identically (an empty table / "no items"
// message), which reads as "there is no data" when it may just not
// have arrived yet. Deterministic-but-varied bar widths (seeded by
// row/column index, not Math.random()) keep the skeleton visually
// alive without literally reshuffling on every re-render.

interface TableSkeletonProps {
  rows?: number;
  columns?: number;
  /** Render the first column as a narrow fixed-width cell (status
   *  dot / chevron) instead of a full-width bar, matching tables that
   *  lead with an icon column. */
  leadingIconColumn?: boolean;
}

export function TableSkeleton({ rows = 6, columns = 4, leadingIconColumn = false }: TableSkeletonProps) {
  return (
    <div role="status" aria-label="Loading" className="divide-y divide-[var(--border)]">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex items-center gap-4 px-5 py-3.5">
          {Array.from({ length: columns }).map((_, c) => {
            if (leadingIconColumn && c === 0) {
              return (
                <span
                  key={c}
                  className="skeleton-shimmer h-3.5 w-3.5 shrink-0 rounded-full"
                  aria-hidden
                />
              );
            }
            const widthPct = 35 + ((r * 17 + c * 23) % 45);
            return (
              <span
                key={c}
                className="skeleton-shimmer h-3 shrink-0 rounded"
                style={{ width: `${widthPct}%`, flex: c === columns - 1 ? "0 1 auto" : "1 1 0%" }}
                aria-hidden
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}
