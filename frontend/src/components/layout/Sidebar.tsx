import { NavLink } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useSystemHealth, type SystemHealthState } from "../../hooks/useSystemHealth";
import { CheckCircleIcon, AlertTriangleIcon, CloseIcon } from "../icons";

const NAV_ITEMS = [
  { to: "/", label: "Overview", exact: true },
  { to: "/telemetry", label: "Live Telemetry" },
  { to: "/alerts", label: "Alerts" },
  { to: "/assets", label: "Assets" },
  { to: "/audit-log", label: "Audit Log" },
];

const HEALTH_COPY: Record<SystemHealthState, { title: string; detail: string }> = {
  checking: { title: "Checking systems…", detail: "Confirming core service status" },
  healthy: { title: "System Healthy", detail: "All core services operational" },
  degraded: { title: "Degraded Service", detail: "One or more core services impaired" },
  unknown: { title: "Status Unknown", detail: "Unable to reach the health check" },
};

interface SidebarProps {
  /** Whether the off-canvas mobile drawer is open. Ignored at md+,
   *  where the sidebar is always visible in-flow. */
  open: boolean;
  onClose: () => void;
}

/**
 * Left app shell navigation. Slimmer and quieter than a typical admin
 * template: inactive items are plain text, the active item gets a
 * subtle tint plus a thin accent indicator bar rather than a filled
 * rectangle, and the bottom system health panel is backed by the
 * real GET /health endpoint (see useSystemHealth) rather than an
 * invented status. Below md it collapses into an off-canvas drawer
 * toggled from the header's menu button.
 */
export function Sidebar({ open, onClose }: SidebarProps) {
  const health = useSystemHealth();
  const healthCopy = HEALTH_COPY[health];
  const HealthIcon = health === "degraded" || health === "unknown" ? AlertTriangleIcon : CheckCircleIcon;
  const healthColor =
    health === "healthy" ? "var(--success)" : health === "degraded" || health === "unknown" ? "var(--high)" : "var(--text-tertiary)";

  return (
    <>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={onClose}
            className="fixed inset-0 z-30 bg-black/60 md:hidden"
            aria-hidden
          />
        )}
      </AnimatePresence>

      <aside
        className={`glass-panel fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col border-r border-[var(--border)] transition-transform duration-200 ease-out md:static md:z-10 md:w-56 md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-5 py-7">
          <div className="flex items-center gap-3">
            <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius-sm)]">
              <span
                aria-hidden
                className="absolute inset-0 rounded-[var(--radius-sm)]"
                style={{
                  background: "radial-gradient(circle at 32% 28%, var(--accent-glow), transparent 72%)",
                  opacity: 0.6,
                }}
              />
              <span
                aria-hidden
                className="absolute inset-0 rounded-[var(--radius-sm)] border border-[var(--accent)]/20"
              />
              <img
                src="/logo-mark.png"
                alt="ForgeSentinel"
                className="relative h-6 w-6 object-contain"
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className="font-mono text-[14px] font-bold leading-none tracking-wider text-[var(--text-primary)]">
                FORGESENTINEL
              </span>
              <span className="text-[9.5px] font-semibold uppercase tracking-[0.18em] text-[var(--text-tertiary)]">
                Industrial Security
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close navigation"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-[var(--text-tertiary)] transition-colors duration-200 hover:text-[var(--text-primary)] md:hidden"
          >
            <CloseIcon className="h-4 w-4" />
          </button>
        </div>

      <nav className="flex flex-col gap-0.5 p-3" aria-label="Primary">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.exact}
            className={({ isActive }) =>
              `relative rounded-md py-2.5 pl-4 pr-3 text-sm transition-colors duration-200 ${
                isActive
                  ? "font-medium text-[var(--text-primary)]"
                  : "font-normal text-[var(--text-tertiary)] hover:bg-white/[0.03] hover:text-[var(--text-secondary)]"
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.span
                    layoutId="nav-active"
                    className="absolute inset-0 rounded-md border border-[var(--accent)]/15 bg-[var(--accent-dim)]"
                    style={{ boxShadow: "inset 0 1px 0 0 rgba(255,255,255,0.05)" }}
                    transition={{ type: "spring", stiffness: 420, damping: 34 }}
                  />
                )}
                {isActive && (
                  <span
                    aria-hidden
                    className="absolute inset-y-1.5 left-0 w-[2px] rounded-full bg-[var(--accent)]"
                  />
                )}
                <span className="relative">{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-2.5 border-t border-[var(--border)] p-3.5">
        <div
          className="surface-2 relative flex items-center gap-2 overflow-hidden rounded-[var(--radius-sm)] border border-[var(--border)] py-2 pl-3 pr-2.5"
          role="status"
        >
          <span aria-hidden className="absolute inset-y-0 left-0 w-[2px]" style={{ background: healthColor }} />
          <HealthIcon className="h-3.5 w-3.5 shrink-0" style={{ color: healthColor }} />
          <div className="min-w-0 leading-tight">
            <div className="truncate text-[11.5px] font-medium text-[var(--text-primary)]">
              {healthCopy.title}
            </div>
            <div className="truncate text-[10px] text-[var(--text-tertiary)]">{healthCopy.detail}</div>
          </div>
        </div>
        <p className="px-0.5 text-[10px] leading-relaxed text-[var(--text-tertiary)]">
          Simulated OT lab. No real industrial systems.
        </p>
      </div>
      </aside>
    </>
  );
}
