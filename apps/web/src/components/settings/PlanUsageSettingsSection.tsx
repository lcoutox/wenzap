"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Zap } from "lucide-react";
import { api } from "@/lib/api";
import type { Subscription, Usage } from "@/lib/api";
import { PlanLimitBar } from "@/components/plan/PlanLimitBar";
import { getLimitState } from "@/lib/plan";

const UPGRADE_MSG =
  "Planos pagos estarão disponíveis em breve. Fale com a equipe para liberar mais uso.";

export function PlanUsageSettingsSection() {
  const [sub, setSub]     = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);

  useEffect(() => {
    api.plans.current().then(setSub).catch(() => {});
    api.plans.usage().then(setUsage).catch(() => {});
  }, []);

  const plan = sub?.plan;

  if (!plan && !usage) {
    return (
      <div className="h-32 flex items-center justify-center text-sm text-nb-muted">
        Carregando…
      </div>
    );
  }

  const creditsState = usage && plan
    ? getLimitState(usage.ai_credits_used, plan.monthly_ai_credits)
    : "normal";
  const atLimit = creditsState === "exceeded";

  return (
    <div className="max-w-2xl space-y-5">
      {/* Plan header */}
      {plan && (
        <div className="bg-nb-panel rounded-2xl border border-nb-border p-5">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-nb-text">{plan.name}</h2>
              <span className="text-[10px] font-bold px-2 py-0.5 bg-nb-primary-bg text-nb-primary-strong rounded-lg border border-nb-primary/20 uppercase tracking-widest">
                {sub?.status}
              </span>
            </div>
            <Link
              href="/dashboard/plan"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-nb-primary-bg border border-nb-primary/20 text-nb-primary-strong hover:bg-nb-primary/20 transition-colors"
            >
              <Zap className="w-3 h-3" />
              Upgrade
            </Link>
          </div>
          {plan.description && (
            <p className="text-sm text-nb-muted mb-0">{plan.description}</p>
          )}
        </div>
      )}

      {/* Resource usage */}
      {plan && usage && (
        <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 space-y-4">
          <h3 className="text-sm font-semibold text-nb-text">Recursos</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <PlanLimitBar label="Agentes"               used={usage.agents_count}           limit={plan.agents_limit} />
            <PlanLimitBar label="Bases de conhecimento" used={usage.knowledge_bases_count}   limit={plan.knowledge_bases_limit} />
            <PlanLimitBar label="Itens do Catálogo"     used={usage.catalog_items_count}     limit={plan.catalog_items_limit} />
            <PlanLimitBar label="Canais"                used={usage.channels_count}          limit={plan.channels_limit} />
          </div>
        </div>
      )}

      {/* Monthly usage */}
      {plan && usage && (
        <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-nb-text">Consumo no período</h3>
            <span className="text-xs text-nb-muted">
              Reinicia em{" "}
              {new Date(usage.period_end).toLocaleDateString("pt-BR", {
                day: "numeric", month: "long",
              })}
            </span>
          </div>
          <PlanLimitBar label="Créditos IA" used={usage.ai_credits_used} limit={plan.monthly_ai_credits} unit="créditos" />
          <div className="pt-2 border-t border-nb-border/50">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-nb-muted">Conversas iniciadas</span>
              <span className="text-xs font-semibold text-nb-text tabular-nums">
                {usage.conversations_count.toLocaleString("pt-BR")}
              </span>
            </div>
            <p className="text-[10px] text-nb-muted mt-1 leading-relaxed">
              Apenas métrica operacional — conversas não são limitadas por plano.
            </p>
          </div>
        </div>
      )}

      {/* Upgrade prompt */}
      {atLimit && (
        <div className="rounded-xl border border-nb-danger/20 bg-nb-danger/5 p-4 flex items-start gap-3">
          <Zap className="w-4 h-4 text-nb-danger flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-nb-text mb-0.5">Limite atingido</p>
            <p className="text-xs text-nb-muted">{UPGRADE_MSG}</p>
          </div>
        </div>
      )}
      {!atLimit && (
        <div className="rounded-xl border border-nb-border bg-nb-elevated/30 p-4 flex items-start gap-3">
          <Zap className="w-4 h-4 text-nb-muted flex-shrink-0 mt-0.5" />
          <p className="text-xs text-nb-muted">{UPGRADE_MSG}</p>
        </div>
      )}
    </div>
  );
}
