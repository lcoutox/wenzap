"use client";

import { Zap } from "lucide-react";
import Link from "next/link";

interface UpgradePromptProps {
  title?: string;
  description?: string;
  /** If true, renders inline rather than as a card */
  inline?: boolean;
  className?: string;
}

const DEFAULT_TITLE = "Recurso Premium";
const DEFAULT_DESC  = "Disponível no plano Growth ou superior.";

export function UpgradePrompt({
  title = DEFAULT_TITLE,
  description = DEFAULT_DESC,
  inline = false,
  className = "",
}: UpgradePromptProps) {
  if (inline) {
    return (
      <p className={`text-xs text-nb-muted ${className}`}>
        {description}{" "}
        <Link href="/dashboard/plan" className="text-nb-primary hover:underline font-medium">
          Ver plano
        </Link>
      </p>
    );
  }

  return (
    <div className={`rounded-xl border border-nb-warning/30 bg-nb-warning/5 p-4 ${className}`}>
      <div className="flex items-start gap-3">
        <div className="w-7 h-7 rounded-lg bg-nb-warning/10 border border-nb-warning/30 flex items-center justify-center flex-shrink-0 mt-0.5">
          <Zap className="w-3.5 h-3.5 text-nb-warning" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-nb-text mb-0.5">{title}</p>
          <p className="text-xs text-nb-muted mb-3">{description}</p>
          <Link
            href="/dashboard/plan"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-nb-warning/10 border border-nb-warning/30 text-nb-warning hover:bg-nb-warning/20 transition-colors"
          >
            <Zap className="w-3 h-3" />
            Ver opções de upgrade
          </Link>
        </div>
      </div>
    </div>
  );
}

/** Small inline "Limite atingido" banner with CTA */
export function LimitReachedBanner({
  resource,
  className = "",
}: {
  resource: string;
  className?: string;
}) {
  return (
    <div className={`flex items-center justify-between gap-3 p-3 rounded-xl border border-nb-danger/20 bg-nb-danger/5 ${className}`}>
      <p className="text-xs text-nb-danger font-medium">
        Você atingiu o limite de <strong>{resource}</strong> do plano Free.
      </p>
      <Link
        href="/dashboard/plan"
        className="flex-shrink-0 text-xs font-semibold text-nb-danger hover:underline"
      >
        Fazer upgrade →
      </Link>
    </div>
  );
}
