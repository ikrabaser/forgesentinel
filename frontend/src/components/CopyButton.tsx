import { useState } from "react";
import { CheckCircleIcon, CopyIcon } from "./icons";

// Generic "copy this text" affordance - the Audit Log's expanded JSON
// details is the first user (an investigator pasting a MODBUS_WRITE
// payload elsewhere), but nothing here is specific to that page.
const CONFIRM_MS = 1500;

export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy(event: React.MouseEvent) {
    event.stopPropagation(); // don't trigger a parent row's expand/collapse
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), CONFIRM_MS);
    } catch {
      // Clipboard access can be denied (permissions, insecure
      // context) - fail quietly rather than surface an error for a
      // convenience action with no destructive consequence.
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="inline-flex items-center gap-1.5 rounded border border-[var(--border-strong)] px-2 py-1 text-[10.5px] text-[var(--text-tertiary)] transition-colors duration-200 hover:border-[var(--accent)]/40 hover:text-[var(--accent)]"
    >
      {copied ? (
        <>
          <CheckCircleIcon className="h-3 w-3" />
          Copied
        </>
      ) : (
        <>
          <CopyIcon className="h-3 w-3" />
          {label}
        </>
      )}
    </button>
  );
}
