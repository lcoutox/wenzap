"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Subscription, Usage } from "@/lib/api";

function fmt(n: number) {
  return n.toLocaleString("pt-BR");
}

export function PlanUsageSettingsSection() {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);

  useEffect(() => {
    api.plans.current().then(setSub).catch(() => {});
    api.plans.usage().then(setUsage).catch(() => {});
  }, []);

  const plan = sub?.plan;

  return (
    <div className="max-w-2xl space-y-4">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-nb-text">Plano e uso</h2>
        <p className="text-xs text-nb-muted mt-0.5">Seu plano atual e consumo do período.</p>
      </div>

      {plan && (
        <div className="bg-nb-panel rounded-2xl border border-nb-border p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-semibold text-nb-text">{plan.name}</h3>
            <span className="text-[10px] font-semibold px-2 py-1 bg-nb-primary-bg text-nb-primary-strong rounded-lg border border-nb-primary/20 uppercase tracking-widest">
              {sub?.status}
            </span>
          </div>
          <p className="text-sm text-nb-muted mb-4">{plan.description}</p>

          <div className="grid grid-cols-2 gap-3">
            {[
              ["Agentes", plan.agents_limit],
              ["Bases de conhecimento", plan.knowledge_bases_limit],
              ["Usuários", plan.users_limit],
              ["Pipelines", plan.pipelines_limit],
              ["Integrações", plan.integrations_limit],
              ["Créditos de IA/mês", plan.monthly_ai_credits],
              ["Conversas/mês", plan.monthly_conversations],
            ].map(([label, value]) => (
              <div key={String(label)} className="text-sm">
                <span className="text-nb-muted">{label}: </span>
                <span className="font-medium text-nb-text">{fmt(Number(value))}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {usage && (
        <div className="bg-nb-panel rounded-2xl border border-nb-border p-5">
          <h3 className="text-sm font-semibold text-nb-text mb-4">Uso no período atual</h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-1">Créditos IA</p>
              <p className="text-2xl font-bold text-nb-text">{fmt(usage.ai_credits_used)}</p>
              {plan && <p className="text-xs text-nb-muted">de {fmt(plan.monthly_ai_credits)}</p>}
            </div>
            <div>
              <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-1">Conversas</p>
              <p className="text-2xl font-bold text-nb-text">{fmt(usage.conversations_count)}</p>
              {plan && <p className="text-xs text-nb-muted">de {fmt(plan.monthly_conversations)}</p>}
            </div>
            <div>
              <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-1">Mensagens</p>
              <p className="text-2xl font-bold text-nb-text">{fmt(usage.messages_count)}</p>
            </div>
          </div>
        </div>
      )}

      {!plan && !usage && (
        <div className="h-32 flex items-center justify-center text-sm text-nb-muted">Carregando...</div>
      )}
    </div>
  );
}
