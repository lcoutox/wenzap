"use client";

import { getLimitState, limitPct } from "@/lib/plan";

const STATE_TRACK: Record<string, string> = {
  normal:   "bg-nb-primary",
  warning:  "bg-nb-warning",
  danger:   "bg-nb-danger",
  exceeded: "bg-nb-danger",
};

const STATE_LABEL: Record<string, string> = {
  normal:   "text-nb-muted",
  warning:  "text-nb-warning",
  danger:   "text-nb-danger",
  exceeded: "text-nb-danger",
};

interface PlanLimitBarProps {
  label: string;
  used: number;
  limit: number;
  /** Override suffix after "de X", e.g. "créditos". Defaults to nothing. */
  unit?: string;
  className?: string;
}

export function PlanLimitBar({ label, used, limit, unit, className = "" }: PlanLimitBarProps) {
  const state = getLimitState(used, limit);
  const pct   = limitPct(used, limit);
  const unlimited = limit <= 0;

  return (
    <div className={className}>
      <div className="flex items-center justify-between mb-1.5">
        <span className={`text-xs font-medium ${STATE_LABEL[state]}`}>{label}</span>
        <span className={`text-xs tabular-nums ${STATE_LABEL[state]}`}>
          {state === "exceeded" ? (
            <span className="font-semibold">Limite atingido</span>
          ) : unlimited ? (
            <span className="text-nb-muted">Ilimitado</span>
          ) : (
            <>
              <span className="font-semibold">{used.toLocaleString("pt-BR")}</span>
              <span className="text-nb-muted"> / {limit.toLocaleString("pt-BR")}{unit ? ` ${unit}` : ""}</span>
            </>
          )}
        </span>
      </div>
      {!unlimited && (
        <div className="h-1.5 rounded-full bg-nb-border overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${STATE_TRACK[state]}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </div>
  );
}
