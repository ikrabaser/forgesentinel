// Thin REST client. Every function returns a typed Promise and throws
// on a non-2xx response - callers (React Query-free, plain useEffect
// hooks here since the app is small) handle loading/error state
// themselves. Relative paths (`/api/...`) rely on Vite's dev proxy
// (see vite.config.ts) so this file never hard-codes a backend host.

import type {
  Alert,
  AlertStatus,
  Asset,
  IncidentAnalysis,
  IncidentAnalysisRequest,
  IncidentAnalysisTaskStatus,
  Telemetry,
} from "./types";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`GET ${path} failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { method: "POST" });
  if (!response.ok) {
    throw new Error(`POST ${path} failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => getJson<{ status: string; database: string }>("/health"),

  listAssets: () => getJson<Asset[]>("/api/assets"),
  getAsset: (assetCode: string) => getJson<Asset>(`/api/assets/${assetCode}`),

  listTelemetry: (assetCode: string, limit = 50) =>
    getJson<Telemetry[]>(
      `/api/telemetry?asset_code=${encodeURIComponent(assetCode)}&limit=${limit}`,
    ),
  latestTelemetry: (assetCode: string) =>
    getJson<Telemetry>(`/api/telemetry/latest?asset_code=${encodeURIComponent(assetCode)}`),

  listAlerts: (status?: AlertStatus, limit = 100) =>
    getJson<Alert[]>(
      `/api/alerts?limit=${limit}${status ? `&status=${status}` : ""}`,
    ),
  acknowledgeAlert: (id: number) => postJson<Alert>(`/api/alerts/${id}/acknowledge`),
  resolveAlert: (id: number) => postJson<Alert>(`/api/alerts/${id}/resolve`),

  // Milestone 14 - AI Incident Analyst. requestIncidentAnalysis kicks
  // off a Celery task (POST) and returns immediately with a task_id;
  // getIncidentAnalysisTask polls Celery's result backend for that
  // task's status. Once it's SUCCESS, the result is also durably
  // stored - listIncidentAnalyses reads that back from Postgres later
  // without needing the (by-then-expired) Celery task id.
  requestIncidentAnalysis: (alertId: number) =>
    postJson<IncidentAnalysisRequest>(`/api/incidents/analyze/${alertId}`),
  getIncidentAnalysisTask: (taskId: string) =>
    getJson<IncidentAnalysisTaskStatus>(`/api/incidents/tasks/${taskId}`),
  listIncidentAnalyses: (alertId: number) =>
    getJson<IncidentAnalysis[]>(`/api/incidents?alert_id=${alertId}`),
};
