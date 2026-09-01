// Mirrors backend/schemas.py exactly. Kept as a separate file (not
// inferred from a runtime schema) so a backend field rename is a
// TypeScript compile error here, not a silently-undefined value in
// the UI - the same "catch drift at build time" reasoning that
// justified keeping Pydantic schemas separate from the ORM models.

export type PumpState = "ON" | "OFF" | "FAULT";

export type AlertSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type AlertStatus = "OPEN" | "ACKNOWLEDGED" | "RESOLVED";

export interface Asset {
  id: number;
  asset_code: string;
  name: string;
  asset_type: string;
  protocol: string | null;
  ip_address: string | null;
  status: "ONLINE" | "OFFLINE" | "UNKNOWN";
  first_seen: string;
  last_seen: string;
}

export interface Telemetry {
  id: number;
  asset_id: number;
  timestamp: string;
  temperature: number;
  pressure: number;
  tank_level_percent: number;
  pump_state: PumpState;
  cooling_active: boolean;
  inlet_open: boolean;
}

export interface Alert {
  id: number;
  asset_id: number;
  rule_id: string;
  severity: AlertSeverity;
  title: string;
  description: string;
  status: AlertStatus;
  created_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

// WebSocket message shapes from backend/broadcaster.py
export type LiveMessage =
  | ({ type: "telemetry"; asset_code: string } & Omit<Telemetry, "asset_id">)
  | ({ type: "alert" } & Alert);

// Mirrors backend/schemas.py's IncidentAnalysis* models (Milestone 14).
export interface IncidentAnalysisRequest {
  task_id: string;
  status: string;
}

// Mirrors detection/ai_analyst.py's IncidentAnalysis Pydantic model -
// this is Claude's structured output, not a hand-rolled shape.
export interface IncidentAnalysisResult {
  summary: string;
  possible_causes: string[];
  recommended_actions: string[];
}

export interface IncidentAnalysisTaskStatus {
  task_id: string;
  // Celery states: PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED
  status: string;
  result: IncidentAnalysisResult | null;
  error: string | null;
}

export interface IncidentAnalysis {
  id: number;
  alert_id: number;
  model: string;
  summary: string;
  possible_causes: string[];
  recommended_actions: string[];
  created_at: string;
}
