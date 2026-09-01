// Posture derivation lives outside the component file so the
// component module only exports a component (keeps Fast Refresh
// happy, same convention as api/types.ts / lib/time.ts).

export type SecurityPosture = "Healthy" | "Guarded" | "Elevated Risk" | "Critical";

export interface SeverityCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

/** Derives a plant-wide posture strictly from real open-alert severity
 *  counts - critical alerts outrank high, which outrank medium, with
 *  no unresolved findings reading as healthy. No fabricated scoring. */
export function derivePosture(counts: SeverityCounts): SecurityPosture {
  if (counts.critical > 0) return "Critical";
  if (counts.high > 0) return "Elevated Risk";
  if (counts.medium > 0) return "Guarded";
  return "Healthy";
}
