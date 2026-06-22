"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Agent, AgentStatus, MemberRole } from "@/lib/api";

const STATUS_LABELS: Record<AgentStatus, string> = {
  draft: "Rascunho",
  active: "Ativo",
  inactive: "Inativo",
  archived: "Arquivado",
};

const STATUS_COLORS: Record<AgentStatus, string> = {
  draft: "bg-gray-100 text-gray-600",
  active: "bg-green-50 text-green-700",
  inactive: "bg-yellow-50 text-yellow-700",
  archived: "bg-red-50 text-red-500",
};

function canCreate(role: MemberRole | null): boolean {
  return role === "owner" || role === "admin" || role === "member";
}

function canWrite(role: MemberRole | null): boolean {
  return role === "owner" || role === "admin" || role === "member";
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
        const [agentList, me] = await Promise.all([
          api.agents.list(token),
          api.me(token),
        ]);
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
    return <p className="text-sm text-gray-400">Carregando agentes...</p>;
  }

  if (error) {
    return <p className="text-sm text-red-500">{error}</p>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Agentes</h1>
        {canCreate(role) && (
          <Link
            href="/dashboard/agents/new"
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
          >
            Novo agente
          </Link>
        )}
      </div>

      {agents.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-gray-200 rounded-lg bg-white">
          <p className="text-gray-500 text-sm mb-4">Nenhum agente criado ainda.</p>
          {canCreate(role) && (
            <Link
              href="/dashboard/agents/new"
              className="inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
            >
              Criar primeiro agente
            </Link>
          )}
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-gray-500 font-medium">Nome</th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium">Status</th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium">Modelo</th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium">Criado em</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {agents.map((agent) => (
                <tr key={agent.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{agent.name}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[agent.status]}`}>
                      {STATUS_LABELS[agent.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {agent.model_provider}/{agent.model_name}
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {new Date(agent.created_at).toLocaleDateString("pt-BR")}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/dashboard/agents/${agent.id}`}
                      className="text-blue-600 hover:underline text-xs font-medium"
                    >
                      {canWrite(role) ? "Editar" : "Ver"}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
