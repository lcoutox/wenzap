"use client";

import { useAuth } from "@clerk/nextjs";
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
    <div className="group bg-white rounded-xl border border-gray-200 hover:border-indigo-300 hover:shadow-md transition-all duration-150 flex flex-col">
      {/* Card header */}
      <div className="p-5 flex items-start gap-4">
        <div className="w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center flex-shrink-0">
          <Bot className="w-5 h-5 text-indigo-500" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-gray-900 truncate">{agent.name}</h3>
            <AgentStatusBadge status={agent.status} />
          </div>
          {agent.description ? (
            <p className="mt-1 text-xs text-gray-500 line-clamp-2">{agent.description}</p>
          ) : (
            <p className="mt-1 text-xs text-gray-300 italic">Sem descrição</p>
          )}
        </div>
      </div>

      {/* Card footer */}
      <div className="px-5 pb-4 mt-auto flex items-center justify-between border-t border-gray-50 pt-3 gap-3">
        <div className="flex items-center gap-3 text-xs text-gray-400 min-w-0">
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
          className="flex-shrink-0 text-xs font-medium text-indigo-600 hover:text-indigo-800 transition-colors"
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
      <div className="w-16 h-16 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-4">
        <Bot className="w-8 h-8 text-indigo-400" />
      </div>
      <h3 className="text-base font-semibold text-gray-900 mb-1">Nenhum agente ainda</h3>
      <p className="text-sm text-gray-500 max-w-xs mb-6">
        Crie seu primeiro agente de IA e conecte-o aos dados e canais da sua empresa.
      </p>
      {canCreate && (
        <Link
          href="/dashboard/agents/new"
          className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Criar primeiro agente
        </Link>
      )}
    </div>
  );
}

export default function AgentsPage() {
  const { getToken } = useAuth();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [role, setRole] = useState<MemberRole | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getToken().then(async (token) => {
      if (!token) return;
      try {
        const [agentList, me] = await Promise.all([api.agents.list(token), api.me(token)]);
        setAgents(agentList);
        setRole(me.role);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Erro ao carregar agentes.");
      } finally {
        setLoading(false);
      }
    });
  }, [getToken]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-36 bg-white rounded-xl border border-gray-200 animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
        {error}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Agentes</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Crie e gerencie agentes de IA para atendimento, vendas e operações.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {agents.length > 0 && (
            <span className="text-sm text-gray-400 font-medium">
              {agents.length} agente{agents.length > 1 ? "s" : ""}
            </span>
          )}
          {canCreate(role) && (
            <Link
              href="/dashboard/agents/new"
              className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
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
