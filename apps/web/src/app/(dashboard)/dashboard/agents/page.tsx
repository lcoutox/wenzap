"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Bot, Plus, Calendar, Cpu } from "lucide-react";
import { api } from "@/lib/api";
import type { Agent, MemberRole } from "@/lib/api";
import { AgentStatusBadge } from "@/components/agents/AgentStatusBadge";

function canCreate(role: MemberRole | null) {
  return role === "owner" || role === "admin" || role === "member";
}
function canWrite(role: MemberRole | null) {
  return role === "owner" || role === "admin" || role === "member";
}

function AgentCard({ agent, role }: { agent: Agent; role: MemberRole | null }) {
  const actionLabel = canWrite(role) ? "Editar" : "Ver detalhes";

  return (
    <div className="group bg-nb-panel rounded-2xl border border-nb-border hover:border-nb-border-strong transition-all duration-150 flex flex-col">
      <div className="p-5 flex items-start gap-4">
        <div className="w-10 h-10 rounded-xl bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center flex-shrink-0 overflow-hidden">
          {agent.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={agent.avatar_url} alt={agent.name} className="w-full h-full object-cover" />
          ) : (
            <Bot className="w-5 h-5 text-nb-primary-strong" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-nb-text truncate">{agent.name}</h3>
            <AgentStatusBadge status={agent.status} />
          </div>
          {agent.description ? (
            <p className="mt-1 text-xs text-nb-muted line-clamp-2">{agent.description}</p>
          ) : (
            <p className="mt-1 text-xs text-nb-muted/40 italic">Sem descrição</p>
          )}
        </div>
      </div>

      <div className="px-5 pb-4 mt-auto flex items-center justify-between border-t border-nb-border pt-3 gap-3">
        <div className="flex items-center gap-3 text-xs text-nb-muted min-w-0">
          <span className="flex items-center gap-1 truncate">
            <Cpu className="w-3 h-3 flex-shrink-0" />
            <span className="truncate">{agent.model_name}</span>
          </span>
          <span className="flex items-center gap-1 flex-shrink-0">
            <Calendar className="w-3 h-3" />
            {new Date(agent.created_at).toLocaleDateString("pt-BR")}
          </span>
        </div>

        <Link
          href={`/dashboard/agents/${agent.id}`}
          className="flex-shrink-0 text-xs font-medium text-nb-primary hover:text-nb-primary-strong transition-colors"
        >
          {actionLabel} →
        </Link>
      </div>
    </div>
  );
}

function EmptyState({ canCreate }: { canCreate: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 rounded-2xl bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center mb-4">
        <Bot className="w-8 h-8 text-nb-primary" />
      </div>
      <h3 className="text-base font-semibold text-nb-text mb-1">Nenhum agente ainda</h3>
      <p className="text-sm text-nb-muted max-w-xs mb-6">
        Crie seu primeiro agente de IA e conecte-o aos dados e canais da sua empresa.
      </p>
      {canCreate && (
        <Link
          href="/dashboard/agents/new"
          className="inline-flex items-center gap-2 px-4 py-2 bg-nb-primary text-white text-sm font-medium rounded-xl hover:bg-nb-primary-strong transition-colors"
        >
          <Plus className="w-4 h-4" />
          Criar primeiro agente
        </Link>
      )}
    </div>
  );
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [role, setRole] = useState<MemberRole | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.agents.list(), api.me()])
      .then(([agentList, me]) => {
        setAgents(agentList);
        setRole(me.role);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Erro ao carregar agentes."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-36 bg-nb-panel rounded-2xl border border-nb-border animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-nb-danger/10 border border-nb-danger/20 rounded-xl text-sm text-nb-danger">
        {error}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-nb-text">Agentes</h1>
          <p className="text-sm text-nb-muted mt-0.5">
            Crie e gerencie agentes de IA para atendimento, vendas e operações.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {agents.length > 0 && (
            <span className="text-sm text-nb-muted font-medium">
              {agents.length} agente{agents.length > 1 ? "s" : ""}
            </span>
          )}
          {canCreate(role) && (
            <Link
              href="/dashboard/agents/new"
              className="inline-flex items-center gap-2 px-4 py-2 bg-nb-primary text-white text-sm font-medium rounded-xl hover:bg-nb-primary-strong transition-colors"
            >
              <Plus className="w-4 h-4" />
              Novo agente
            </Link>
          )}
        </div>
      </div>

      {agents.length === 0 ? (
        <EmptyState canCreate={canCreate(role)} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((agent) => (
            <AgentCard key={agent.id} agent={agent} role={role} />
          ))}
        </div>
      )}
    </div>
  );
}
