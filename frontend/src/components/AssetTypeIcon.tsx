import type { SVGProps } from "react";
import { CpuIcon, DropletIcon, GaugeIcon, PumpIcon, ThermometerIcon, ServerIcon } from "./icons";

type IconComponent = (props: SVGProps<SVGSVGElement>) => ReturnType<typeof CpuIcon>;

// Mirrors db/models.py's AssetType enum values exactly.
const ICON_BY_TYPE: Record<string, IconComponent> = {
  PLC: CpuIcon,
  TANK: DropletIcon,
  PUMP: PumpIcon,
  TEMPERATURE_SENSOR: ThermometerIcon,
  PRESSURE_SENSOR: GaugeIcon,
};

export function AssetTypeIcon({ assetType, className }: { assetType: string; className?: string }) {
  const Icon = ICON_BY_TYPE[assetType] ?? ServerIcon; // unknown future type -> generic device glyph
  return <Icon className={className} />;
}
