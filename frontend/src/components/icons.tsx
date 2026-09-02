import type { SVGProps } from "react";

/**
 * Hand-rolled icon set, not a dependency. The app has no icon library
 * (only unrelated social-link glyphs in public/icons.svg), and the
 * redesign brief explicitly asks not to install a new UI dependency
 * for a handful of restrained, single-purpose glyphs. Every icon
 * shares one visual style (24x24, currentColor stroke, rounded caps)
 * so they read as one system wherever they're used.
 */
type IconProps = SVGProps<SVGSVGElement>;

function base(props: IconProps) {
  return {
    xmlns: "http://www.w3.org/2000/svg",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.75,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
    ...props,
  };
}

/** Compact geometric shield mark used as the brand glyph in the
 *  sidebar - a faceted shield outline with a small forge spark at
 *  its center, distinct from ShieldCheckIcon/ShieldAlertIcon which
 *  carry status meaning elsewhere in the UI. */
export function BrandMarkIcon(props: IconProps) {
  return (
    <svg {...base(props)} strokeWidth={1.5}>
      <path d="M12 3 19 5.5V11c0 4.8-2.9 8.2-7 9.5-4.1-1.3-7-4.7-7-9.5V5.5z" />
      <path d="M12 8.5v3M10.5 13.5h3" />
    </svg>
  );
}

export function BellIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M6 8a6 6 0 1 1 12 0c0 4 1.5 5.5 2 6.5H4c.5-1 2-2.5 2-6.5" />
      <path d="M9.5 18a2.5 2.5 0 0 0 5 0" />
    </svg>
  );
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="m9 6 6 6-6 6" />
    </svg>
  );
}

export function MenuIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4 6.5h16M4 12h16M4 17.5h16" />
    </svg>
  );
}

export function CloseIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}

export function ServerIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="3.5" y="4" width="17" height="6.5" rx="1.5" />
      <rect x="3.5" y="13.5" width="17" height="6.5" rx="1.5" />
      <path d="M7 7.25h.01M7 16.75h.01" />
    </svg>
  );
}

export function RadioIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="12" cy="12" r="2" />
      <path d="M8.5 15.5a5 5 0 0 1 0-7M15.5 8.5a5 5 0 0 1 0 7M5.5 18.5a9 9 0 0 1 0-13M18.5 5.5a9 9 0 0 1 0 13" />
    </svg>
  );
}

export function AlertTriangleIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 4.5 21 19.5H3z" />
      <path d="M12 10v4.5M12 17.25h.01" />
    </svg>
  );
}

export function ShieldCheckIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 3.5 5 6v5.5c0 4.6 3 7.7 7 9 4-1.3 7-4.4 7-9V6z" />
      <path d="m9 12 2.2 2.2L15.5 10" />
    </svg>
  );
}

export function ShieldAlertIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 3.5 5 6v5.5c0 4.6 3 7.7 7 9 4-1.3 7-4.4 7-9V6z" />
      <path d="M12 8.5v4M12 15.75h.01" />
    </svg>
  );
}

export function ArrowUpRightIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M7 17 17 7M9 7h8v8" />
    </svg>
  );
}

export function CheckCircleIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m8.5 12.3 2.3 2.3 4.7-5" />
    </svg>
  );
}

export function InboxIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4 12.5 6.5 5h11L20 12.5" />
      <path d="M4 12.5V18a1.5 1.5 0 0 0 1.5 1.5h13A1.5 1.5 0 0 0 20 18v-5.5" />
      <path d="M4 12.5h4.5l1 2h5l1-2H20" />
    </svg>
  );
}

// Asset-type glyphs (AssetTypeIcon.tsx) - one per AssetType value from
// db/models.py, so the Assets table reads at a glance instead of
// requiring the "Type" column text to be read for every row.

export function CpuIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="7" y="7" width="10" height="10" rx="1.5" />
      <path d="M9.5 4v2.2M14.5 4v2.2M9.5 17.8V20M14.5 17.8V20M4 9.5h2.2M4 14.5h2.2M17.8 9.5H20M17.8 14.5H20" />
    </svg>
  );
}

export function DropletIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 3.5c3 3.7 6 7.4 6 10.8a6 6 0 1 1-12 0c0-3.4 3-7.1 6-10.8z" />
    </svg>
  );
}

export function PumpIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="10.5" cy="12" r="6" />
      <path d="M16 9.5 20 6M20 6v3.2M20 6h-3.2" />
    </svg>
  );
}

export function ThermometerIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 4.5a2 2 0 0 0-2 2v8.1a3.5 3.5 0 1 0 4 0V6.5a2 2 0 0 0-2-2z" />
      <path d="M12 12.5v3" />
    </svg>
  );
}

export function GaugeIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4.5 15.5a7.5 7.5 0 1 1 15 0" />
      <path d="M12 15.5 15 11" />
      <path d="M12 15.5h.01" />
    </svg>
  );
}

export function CopyIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="8.5" y="8.5" width="11" height="11" rx="1.5" />
      <path d="M15.5 8.5V6.5A1.5 1.5 0 0 0 14 5H6a1.5 1.5 0 0 0-1.5 1.5V14A1.5 1.5 0 0 0 6 15.5h2" />
    </svg>
  );
}

/** Used only on the AI Incident Analyst trigger/panel (Milestone 14) -
 *  a distinct glyph so an AI-generated explanation is visually
 *  unmistakable from anything the system itself asserts as fact. */
export function SparklesIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 4.5 13.4 9l4.6 1.4-4.6 1.4L12 16.3 10.6 11.8 6 10.4l4.6-1.4z" />
      <path d="M19 4v3M17.5 5.5h3" />
    </svg>
  );
}
