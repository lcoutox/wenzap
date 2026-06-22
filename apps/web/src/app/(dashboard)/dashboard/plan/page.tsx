"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Subscription, Usage } from "@/lib/api";

function fmt(n: number) {
  return n.toLocaleString("pt-BR");
}

export default function PlanPage() {
  const { getToken } = useAuth();
  const [sub, setSub] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);

  useEffect(() => {
    getToken().then((token) => {
      if (!token) return;
      api.plans.current(token).then(setSub);
      api.plans.usage(token).then(setUsage);
    });
  }, [getToken]);

  const plan = sub?.plan;

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Plano e uso</h1>

      {plan && (
        <div className="bg-white rounded-lg border border-gray-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold text-gray-900">{plan.name}</h2>
            <span className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded font-medium uppercase">
              {sub?.status}
            </span>
          </div>
          <p className="text-sm text-gray-500 mb-4">{plan.description}</p>

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
                <span className="text-gray-500">{label}: </span>
                <span className="font-medium text-gray-900">{fmt(Number(value))}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {usage && (
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-base font-semibold text-gray-900 mb-4">Uso no período atual</h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-gray-500 mb-1">Créditos de IA usados</p>
              <p className="text-2xl font-bold text-gray-900">{fmt(usage.ai_credits_used)}</p>
              {plan && (
                <p className="text-xs text-gray-400">de {fmt(plan.monthly_ai_credits)}</p>
              )}
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Conversas</p>
              <p className="text-2xl font-bold text-gray-900">{fmt(usage.conversations_count)}</p>
              {plan && (
                <p className="text-xs text-gray-400">de {fmt(plan.monthly_conversations)}</p>
              )}
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Mensagens</p>
              <p className="text-2xl font-bold text-gray-900">{fmt(usage.messages_count)}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
