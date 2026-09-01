import { motion } from "framer-motion";
import { StatusDot } from "../StatusDot";
import { NotificationCenter } from "../NotificationCenter";
import { MenuIcon } from "../icons";
import { useLiveData } from "../../state/LiveDataContext";
import { timeAgo } from "../../lib/time";

const STATUS_LABEL: Record<string, string> = {
  connected: "LIVE",
  connecting: "CONNECTING",
  disconnected: "RECONNECTING",
};

interface TopBarProps {
  title: string;
  subtitle?: string;
  onMenuClick: () => void;
}

export function TopBar({ title, subtitle, onMenuClick }: TopBarProps) {
  const { connectionState, lastMessageAt } = useLiveData();

  return (
    <header className="glass-panel relative z-10 flex items-center justify-between gap-4 border-b border-[var(--border)] px-4 py-3.5 sm:px-8">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onMenuClick}
          aria-label="Open navigation"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-[var(--border)] text-[var(--text-secondary)] transition-colors duration-200 hover:border-[var(--border-strong)] hover:text-[var(--text-primary)] md:hidden"
        >
          <MenuIcon className="h-4 w-4" />
        </button>
        <div className="min-w-0">
          <motion.h1
            key={title}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.2 }}
            className="truncate text-[23px] font-semibold tracking-tight text-[var(--text-primary)]"
          >
            {title}
          </motion.h1>
          {subtitle && (
            <p className="mt-0.5 truncate text-[13px] text-[var(--text-secondary)]">{subtitle}</p>
          )}
        </div>
      </div>

      {/* Right cluster: sync/status grouped in one bordered pill (a
          divider between the two pieces of live-connection info),
          the notification bell standing apart as its own action. */}
      <div className="flex shrink-0 items-center gap-2.5">
        <div
          className="flex items-center gap-2 rounded-full border border-[var(--border-strong)] bg-[var(--surface-2)] py-1.5 pl-3 pr-2.5 font-mono text-[11px] font-medium tracking-wide text-[var(--text-secondary)]"
          role="status"
        >
          <StatusDot online={connectionState === "connected"} />
          {STATUS_LABEL[connectionState]}
          {lastMessageAt && (
            <>
              <span aria-hidden className="h-3 w-px bg-[var(--border-strong)]" />
              <span className="hidden text-[var(--text-tertiary)] lg:inline">
                Last sync {timeAgo(new Date(lastMessageAt).toISOString())}
              </span>
            </>
          )}
        </div>

        <NotificationCenter />
      </div>
    </header>
  );
}
