import { useEffect, useRef } from "react";
import { animate, motion, useMotionValue, useTransform } from "framer-motion";

interface AnimatedNumberProps {
  value: number;
  decimals?: number;
  suffix?: string;
}

/**
 * Smoothly tweens between values instead of snapping - the small
 * touch that makes a live-updating stat card feel alive rather than
 * flickering. Cheap to justify here: these numbers change constantly
 * (temperature every second), so a plain re-render would otherwise
 * jump every time.
 */
export function AnimatedNumber({ value, decimals = 0, suffix = "" }: AnimatedNumberProps) {
  const motionValue = useMotionValue(value);
  // Combine the formatted number and suffix into ONE transformed
  // string - a motion component can bind directly to a single
  // MotionValue child and update the DOM text node without
  // re-rendering React, but that trick only works with one child, not
  // a mix of a MotionValue and a plain string.
  const displayValue = useTransform(motionValue, (v) => `${v.toFixed(decimals)}${suffix}`);
  const previous = useRef(value);

  useEffect(() => {
    const controls = animate(motionValue, value, { duration: 0.6, ease: "easeOut" });
    previous.current = value;
    return controls.stop;
  }, [value, motionValue]);

  return <motion.span className="font-mono tabular-nums">{displayValue}</motion.span>;
}
