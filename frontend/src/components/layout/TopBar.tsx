import { motion } from "framer-motion";
import { StatusDot } from "../StatusDot";
import { useLiveData } from "../../state/LiveDataContext";

const LABELS: Record<string, string> = {
  connected: "Live",
  connecting: "Connecting…",
  disconnected: "Reconnecting…",
};

export function TopBar({ title, subtitle }: { title: string; subtitle?: string }) {
  const { connectionState } = useLiveData();

  return (
    <header className="glass-panel relative z-10 flex items-center justify-between border-b border-[var(--border)] px-8 py-5">
      <div>
        <motion.h1
          key={title}
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.2 }}
          className="text-xl font-bold tracking-tight text-[var(--text-bright)]"
        >
          {title}
        </motion.h1>
        {subtitle && <p className="mt-0.5 text-[13px] text-[var(--text-dim)]">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-2 rounded-full border border-[var(--border-strong)] bg-white/[0.03] px-3 py-1.5 font-mono text-xs text-[var(--text-dim)]">
        <StatusDot online={connectionState === "connected"} />
        {LABELS[connectionState]}
      </div>
    </header>
  );
}
