import { motion } from "framer-motion";

interface StatusDotProps {
  online: boolean;
  size?: number;
}

/**
 * A pulsing status indicator, the same visual language as a real
 * HMI's "device alive" light. The pulse ring only animates when
 * online=true - a dead/offline device shouldn't look alive.
 */
export function StatusDot({ online, size = 8 }: StatusDotProps) {
  const color = online ? "var(--status-online)" : "var(--status-offline)";

  return (
    <span className="relative inline-flex" style={{ width: size, height: size }}>
      {online && (
        <motion.span
          className="absolute inline-flex h-full w-full rounded-full"
          style={{ background: color }}
          animate={{ scale: [1, 2.2], opacity: [0.6, 0] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
        />
      )}
      <span
        className="relative inline-flex rounded-full h-full w-full"
        style={{ background: color }}
      />
    </span>
  );
}
