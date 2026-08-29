import { NavLink } from "react-router-dom";
import { motion } from "framer-motion";

const NAV_ITEMS = [
  { to: "/", label: "Overview", exact: true },
  { to: "/telemetry", label: "Live Telemetry" },
  { to: "/alerts", label: "Alerts" },
  { to: "/assets", label: "Assets" },
];

export function Sidebar() {
  return (
    <aside className="glass-panel relative z-10 flex w-60 shrink-0 flex-col border-r border-[var(--border)]">
      <div className="flex items-center gap-2.5 border-b border-[var(--border)] px-6 py-6">
        <div className="relative flex h-6 w-6 items-center justify-center">
          <span className="absolute h-full w-full animate-pulse rounded-md bg-[var(--accent)] opacity-20 blur-sm" />
          <span className="relative h-2.5 w-2.5 rounded-sm bg-[var(--accent)] shadow-[0_0_12px_var(--accent-glow)]" />
        </div>
        <span className="font-mono text-[15px] font-bold tracking-wider text-[var(--text-bright)]">
          FORGESENTINEL
        </span>
      </div>
      <nav className="flex flex-col gap-1 p-3">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.exact}
            className={({ isActive }) =>
              `relative rounded-md px-3.5 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? "text-[var(--text-bright)]"
                  : "text-[var(--text-dim)] hover:text-[var(--text)]"
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.span
                    layoutId="nav-active-pill"
                    className="absolute inset-0 rounded-md border border-[var(--accent)]/25 bg-[var(--accent-dim)]"
                    transition={{ type: "spring", stiffness: 400, damping: 32 }}
                  />
                )}
                <span className="relative">{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto border-t border-[var(--border)] p-5 text-[11px] leading-relaxed text-[var(--text-dim)]">
        Simulated OT lab.
        <br />
        No real industrial systems.
      </div>
    </aside>
  );
}
