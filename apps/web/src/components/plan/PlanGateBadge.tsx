"use client";

import { Lock, Zap } from "lucide-react";

interface PlanGateBadgeProps {
  /** e.g. "Growth" or "plano Growth" */
  label?: string;
  variant?: "premium" | "locked";
  size?: "xs" | "sm";
}

export function PlanGateBadge({
  label = "Premium",
  variant = "premium",
  size = "xs",
}: PlanGateBadgeProps) {
  const base = size === "xs"
    ? "inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide"
    : "inline-flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-semibold";

  if (variant === "locked") {
    return (
      <span className={`${base} bg-nb-elevated border border-nb-border text-nb-muted`}>
        <Lock className={size === "xs" ? "w-2.5 h-2.5" : "w-3 h-3"} />
        {label}
      </span>
    );
  }

  return (
    <span className={`${base} bg-nb-warning/10 border border-nb-warning/30 text-nb-warning`}>
      <Zap className={size === "xs" ? "w-2.5 h-2.5" : "w-3 h-3"} />
      {label}
    </span>
  );
}
