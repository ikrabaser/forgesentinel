// Shared timestamp formatting. Pulled out of individual pages so
// "time ago" / clock formatting is defined once and stays consistent
// across the incident feed, assets table and telemetry chart rather
// than drifting into slightly different implementations.

export function timeAgo(iso: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function formatClockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour12: false });
}
