import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "../api/client";
import type { AuditLogEntry } from "../api/types";
import { ActionBadge } from "../components/ActionBadge";
import { CopyButton } from "../components/CopyButton";
import { ChevronRightIcon, InboxIcon } from "../components/icons";
import { TableSkeleton } from "../components/TableSkeleton";
import { formatClockTime, timeAgo } from "../lib/time";

const ACTIONS = [
  "ALERT_ACKNOWLEDGED",
  "ALERT_RESOLVED",
  "INCIDENT_ANALYSIS_REQUESTED",
  "MODBUS_WRITE",
] as const;

const RESOURCE_TYPES = ["alert", "plc"] as const;

// Polled, not pushed over the live WebSocket - backend/broadcaster.py
// (Milestone 8) only ever fans out telemetry/alert messages, and
// widening that for one monitoring page isn't worth the coupling
// right now. A 4s poll keeps this page reasonably fresh without it.
const POLL_MS = 4000;
// How long a newly-arrived row keeps its "just landed" highlight
// before fading back to the normal row style.
const HIGHLIGHT_MS = 2500;

export function AuditLogPage() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [action, setAction] = useState<string>("");
  const [resourceType, setResourceType] = useState<string>("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [highlightedIds, setHighlightedIds] = useState<Set<number>>(new Set());

  // Ids already seen at least once, so we can tell "genuinely new
  // since the last poll" apart from "the initial load" - flashing
  // every row the first time the page opens would be noise, not a
  // signal. Not reset on filter change on purpose: switching filters
  // reveals rows that already existed, which isn't "new" either.
  const seenIds = useRef<Set<number> | null>(null);

  useEffect(() => {
    let cancelled = false;

    function load() {
      api
        .listAuditLog({ action: action || undefined, resourceType: resourceType || undefined })
        .then((data) => {
          if (cancelled) return;

          if (seenIds.current !== null) {
            const freshlyArrived = data.filter((e) => !seenIds.current!.has(e.id)).map((e) => e.id);
            if (freshlyArrived.length > 0) {
              setHighlightedIds((prev) => new Set([...prev, ...freshlyArrived]));
              window.setTimeout(() => {
                setHighlightedIds((prev) => {
                  const next = new Set(prev);
                  for (const id of freshlyArrived) next.delete(id);
                  return next;
                });
              }, HIGHLIGHT_MS);
            }
          }
          seenIds.current = new Set(data.map((e) => e.id));

          setEntries(data);
          setLoading(false);
        })
        .catch(() => {
          if (!cancelled) setLoading(false);
        });
    }

    load();
    const interval = window.setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [action, resourceType]);

  return (
    <div className="flex flex-col gap-5 p-8">
      <div className="flex flex-wrap items-center gap-3">
        <FilterSelect
          label="Action"
          value={action}
          onChange={setAction}
          options={ACTIONS as unknown as string[]}
        />
        <FilterSelect
          label="Resource"
          value={resourceType}
          onChange={setResourceType}
          options={RESOURCE_TYPES as unknown as string[]}
        />
        <span className="ml-auto text-[11px] text-[var(--text-tertiary)]">
          {entries.length} {entries.length === 1 ? "entry" : "entries"} · refreshes every{" "}
          {POLL_MS / 1000}s
        </span>
      </div>

      <div className="glass-panel overflow-hidden rounded-xl border border-[var(--border)]">
        {loading ? (
          <TableSkeleton rows={6} columns={5} leadingIconColumn />
        ) : entries.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-[var(--border)] text-[11px] uppercase tracking-wider text-[var(--text-dim)]">
              <tr>
                <th className="w-8 px-5 py-3" />
                <th className="px-5 py-3">Time</th>
                <th className="px-5 py-3">Actor</th>
                <th className="px-5 py-3">Action</th>
                <th className="px-5 py-3">Resource</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, i) => {
                const expanded = expandedId === entry.id;
                return (
                  <AuditRow
                    key={entry.id}
                    entry={entry}
                    index={i}
                    expanded={expanded}
                    isNew={highlightedIds.has(entry.id)}
                    onToggle={() => setExpandedId(expanded ? null : entry.id)}
                  />
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function AuditRow({
  entry,
  index,
  expanded,
  isNew,
  onToggle,
}: {
  entry: AuditLogEntry;
  index: number;
  expanded: boolean;
  isNew: boolean;
  onToggle: () => void;
}) {
  const hasDetails = entry.details !== null && Object.keys(entry.details).length > 0;

  return (
    <>
      <motion.tr
        initial={{ opacity: 0 }}
        animate={{
          opacity: 1,
          backgroundColor: isNew ? "color-mix(in srgb, var(--accent) 12%, transparent)" : "transparent",
        }}
        transition={{
          opacity: { delay: Math.min(index, 12) * 0.02 },
          // Snap to the highlight almost instantly, then ease back out
          // over HIGHLIGHT_MS - a fast attack, slow decay is what
          // reads as "flash" rather than "fade in and out symmetrically".
          backgroundColor: { duration: isNew ? 0.15 : 1.2, ease: "easeOut" },
        }}
        onClick={hasDetails ? onToggle : undefined}
        className={`border-b border-[var(--border)] last:border-b-0 ${
          hasDetails ? "cursor-pointer hover:bg-white/[0.02]" : ""
        }`}
      >
        <td className="px-5 py-3 text-[var(--text-tertiary)]">
          {hasDetails && (
            <ChevronRightIcon
              className={`h-3.5 w-3.5 transition-transform duration-200 ${expanded ? "rotate-90" : ""}`}
            />
          )}
        </td>
        <td className="px-5 py-3 font-mono text-[var(--text-secondary)]" title={entry.timestamp}>
          <span className="text-[var(--text-bright)]">{formatClockTime(entry.timestamp)}</span>{" "}
          <span className="text-[var(--text-tertiary)]">· {timeAgo(entry.timestamp)}</span>
        </td>
        <td className="px-5 py-3 font-mono text-[var(--text-dim)]">{entry.actor}</td>
        <td className="px-5 py-3">
          <ActionBadge action={entry.action} />
        </td>
        <td className="px-5 py-3 font-mono text-[var(--text-dim)]">
          {entry.resource_type}:{entry.resource_id}
        </td>
      </motion.tr>
      <AnimatePresence initial={false}>
        {expanded && hasDetails && (
          <motion.tr
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18 }}
          >
            <td colSpan={5} className="border-b border-[var(--border)] bg-black/20 px-5 py-3">
              <div className="mb-2 flex justify-end">
                <CopyButton value={JSON.stringify(entry.details, null, 2)} label="Copy JSON" />
              </div>
              <pre className="overflow-x-auto font-mono text-[11px] leading-relaxed text-[var(--text-secondary)]">
                {JSON.stringify(entry.details, null, 2)}
              </pre>
            </td>
          </motion.tr>
        )}
      </AnimatePresence>
    </>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}) {
  return (
    <label className="flex items-center gap-2 text-[11px] text-[var(--text-tertiary)]">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="surface-2 rounded-md border border-[var(--border)] bg-transparent px-2.5 py-1.5 font-mono text-[11px] text-[var(--text-secondary)] outline-none transition-colors focus:border-[var(--accent)]/40"
      >
        <option value="">All</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </label>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center">
      <InboxIcon className="h-8 w-8 text-[var(--text-tertiary)]" />
      <p className="text-sm text-[var(--text-dim)]">No audit entries yet.</p>
      <p className="max-w-xs text-[11px] text-[var(--text-tertiary)]">
        Acknowledge or resolve an alert, request an AI analysis, or send a Modbus write to see
        entries appear here.
      </p>
    </div>
  );
}
