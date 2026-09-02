// Loading placeholder matching StatCard's exact structure (label row +
// icon slot, big value line, hint line) so the Overview page doesn't
// visually jump when real data replaces it - the skeleton IS the
// card's shape, not a generic box standing in for it.

export function StatCardSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading"
      className="glass-panel relative overflow-hidden rounded-[var(--radius-md)] border border-[var(--border)] p-6"
    >
      <div className="flex items-start justify-between gap-3">
        <span className="skeleton-shimmer h-2.5 w-16 rounded" aria-hidden />
        <span className="skeleton-shimmer h-8 w-8 shrink-0 rounded-[var(--radius-sm)]" aria-hidden />
      </div>
      <span className="mt-3 block h-8 w-14 skeleton-shimmer rounded" aria-hidden />
      <span className="mt-2.5 block h-3 w-24 skeleton-shimmer rounded" aria-hidden />
    </div>
  );
}
