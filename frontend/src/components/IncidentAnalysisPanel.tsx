import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "../api/client";
import type { IncidentAnalysis, IncidentAnalysisResult } from "../api/types";
import { SparklesIcon } from "./icons";

interface IncidentAnalysisPanelProps {
  alertId: number;
}

type Phase = "idle" | "loading" | "polling" | "done" | "error";

const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 60_000;

/**
 * Milestone 14 - AI Incident Analyst, surfaced per-alert. Requests an
 * analysis (POST -> Celery task), polls until it completes, and
 * renders the result. On mount it also checks for a PAST persisted
 * analysis (GET /api/incidents?alert_id=...) so re-opening an alert
 * doesn't lose - or re-pay for - a prior run.
 *
 * The disclaimer text isn't decorative: the project's own
 * architectural rule is that AI may analyze/explain/recommend but
 * must never control the PLC. This panel only ever renders text a
 * human reads - there is no button here that turns a
 * recommended_action into an executed command.
 */
export function IncidentAnalysisPanel({ alertId }: IncidentAnalysisPanelProps) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<IncidentAnalysisResult | IncidentAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    api
      .listIncidentAnalyses(alertId)
      .then((analyses) => {
        if (!mountedRef.current || analyses.length === 0) return;
        setResult(analyses[0]);
        setPhase("done");
      })
      .catch(() => {
        /* no past analysis available - stay idle, that's fine */
      });
    return () => {
      mountedRef.current = false;
    };
  }, [alertId]);

  async function runAnalysis() {
    setPhase("loading");
    setError(null);
    try {
      const { task_id } = await api.requestIncidentAnalysis(alertId);
      setPhase("polling");

      const deadline = Date.now() + POLL_TIMEOUT_MS;
      while (Date.now() < deadline) {
        const status = await api.getIncidentAnalysisTask(task_id);
        if (!mountedRef.current) return;

        if (status.status === "SUCCESS" && status.result) {
          setResult(status.result);
          setPhase("done");
          return;
        }
        if (status.status === "FAILURE") {
          setError(status.error ?? "Analysis failed.");
          setPhase("error");
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
      }
      if (mountedRef.current) {
        setError("Analysis is taking longer than expected - try again shortly.");
        setPhase("error");
      }
    } catch {
      if (mountedRef.current) {
        setError("Could not reach the analysis service.");
        setPhase("error");
      }
    }
  }

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-black/20 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-[12px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
          <SparklesIcon className="h-3.5 w-3.5 text-[var(--accent)]" />
          AI Incident Analysis
        </div>
        {phase !== "loading" && phase !== "polling" && (
          <button
            onClick={runAnalysis}
            className="rounded border border-[var(--border-strong)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)] transition-colors duration-200 hover:border-[var(--accent)]/50 hover:text-[var(--accent)]"
          >
            {phase === "done" ? "Re-analyze" : "Analyze with AI"}
          </button>
        )}
      </div>

      <AnimatePresence mode="wait">
        {(phase === "loading" || phase === "polling") && (
          <motion.p
            key="pending"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="mt-3 text-[12.5px] text-[var(--text-tertiary)]"
          >
            {phase === "loading" ? "Requesting analysis..." : "Claude is analyzing this incident..."}
          </motion.p>
        )}

        {phase === "error" && (
          <motion.p
            key="error"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="mt-3 text-[12.5px] text-[var(--critical)]"
          >
            {error}
          </motion.p>
        )}

        {phase === "done" && result && (
          <motion.div
            key="result"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-3 flex flex-col gap-3"
          >
            <p className="text-[13px] leading-relaxed text-[var(--text-primary)]">
              {result.summary}
            </p>

            {result.possible_causes.length > 0 && (
              <div>
                <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
                  Possible causes
                </div>
                <ul className="flex flex-col gap-1">
                  {result.possible_causes.map((cause, i) => (
                    <li key={i} className="text-[12.5px] text-[var(--text-secondary)]">
                      • {cause}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.recommended_actions.length > 0 && (
              <div>
                <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
                  Recommended investigation steps
                </div>
                <ul className="flex flex-col gap-1">
                  {result.recommended_actions.map((action, i) => (
                    <li key={i} className="text-[12.5px] text-[var(--text-secondary)]">
                      • {action}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <p className="text-[10.5px] text-[var(--text-tertiary)]">
              AI-generated analysis for human review only - it does not act on the plant. Verify
              against the live telemetry and asset state before making any changes.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
