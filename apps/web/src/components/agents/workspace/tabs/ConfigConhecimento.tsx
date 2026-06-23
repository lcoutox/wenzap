"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BookOpen, Check, Info, Loader2, Minus, Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { AgentKnowledgeBase, KnowledgeBase, MemberRole } from "@/lib/api";

function canWrite(role: MemberRole | null) {
  return role === "owner" || role === "admin" || role === "member";
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function KbStatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    active:   { label: "Ativa",   cls: "bg-green-50 text-green-700 border-green-200" },
    inactive: { label: "Inativa", cls: "bg-gray-50 text-gray-500 border-gray-200" },
    archived: { label: "Arquivada", cls: "bg-red-50 text-red-600 border-red-200" },
  };
  const s = map[status] ?? { label: status, cls: "bg-gray-50 text-gray-500 border-gray-200" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${s.cls}`}>
      {s.label}
    </span>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ConfigConhecimento({
  agentId,
  role,
  getToken,
}: {
  agentId: string;
  role: MemberRole | null;
  getToken: () => Promise<string | null>;
}) {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [connections, setConnections] = useState<AgentKnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [actionErrors, setActionErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    getToken().then(async (token) => {
      if (!token) return;
      try {
        const [allKbs, agentKbs] = await Promise.all([
          api.knowledgeBases.list(token),
          api.agents.knowledgeBases.list(token, agentId),
        ]);
        setKbs(allKbs);
        setConnections(agentKbs);
      } catch (e) {
        setLoadError(e instanceof Error ? e.message : "Erro ao carregar bases de conhecimento.");
      } finally {
        setLoading(false);
      }
    });
  }, [agentId, getToken]);

  function getConnection(kbId: string): AgentKnowledgeBase | undefined {
    return connections.find((c) => c.knowledge_base_id === kbId);
  }

  async function handleConnect(kbId: string) {
    setBusy((p) => ({ ...p, [kbId]: true }));
    setActionErrors((p) => ({ ...p, [kbId]: "" }));
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      const conn = await api.agents.knowledgeBases.connect(token, agentId, kbId);
      setConnections((prev) => {
        const existing = prev.find((c) => c.knowledge_base_id === kbId);
        if (existing) return prev.map((c) => (c.knowledge_base_id === kbId ? conn : c));
        return [...prev, conn];
      });
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        // Already connected — refresh list silently
        try {
          const token2 = await getToken();
          if (token2) {
            const refreshed = await api.agents.knowledgeBases.list(token2, agentId);
            setConnections(refreshed);
          }
        } catch {
          // ignore refresh error
        }
      } else {
        const msg = e instanceof Error ? e.message : "Erro ao conectar.";
        setActionErrors((p) => ({ ...p, [kbId]: msg }));
      }
    } finally {
      setBusy((p) => ({ ...p, [kbId]: false }));
    }
  }

  async function handleDisconnect(kbId: string) {
    setBusy((p) => ({ ...p, [kbId]: true }));
    setActionErrors((p) => ({ ...p, [kbId]: "" }));
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      await api.agents.knowledgeBases.disconnect(token, agentId, kbId);
      setConnections((prev) => prev.filter((c) => c.knowledge_base_id !== kbId));
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Erro ao desconectar.";
      setActionErrors((p) => ({ ...p, [kbId]: msg }));
    } finally {
      setBusy((p) => ({ ...p, [kbId]: false }));
    }
  }

  if (loading) {
    return (
      <div className="space-y-3 animate-pulse">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 bg-gray-100 rounded-xl border border-gray-200" />
        ))}
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600">
        {loadError}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900">Conhecimento do agente</h3>
        <p className="mt-1 text-xs text-gray-500">
          Conecte bases de conhecimento que este agente poderá usar nas próximas fases para
          responder com informações da empresa.
        </p>
      </div>

      {/* RAG warning */}
      <div className="flex items-start gap-2.5 p-3 rounded-lg bg-amber-50 border border-amber-200">
        <Info className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-amber-700">
          As bases conectadas ainda não são usadas nas respostas. Isso será ativado na próxima
          fase de RAG.
        </p>
      </div>

      {/* Empty state — no KBs at all */}
      {kbs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center border border-dashed border-gray-200 rounded-xl">
          <div className="w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-3">
            <BookOpen className="w-6 h-6 text-indigo-400" />
          </div>
          <p className="text-sm font-medium text-gray-700 mb-1">
            Nenhuma base de conhecimento criada ainda.
          </p>
          <p className="text-xs text-gray-500 mb-4">
            Crie uma em{" "}
            <Link
              href="/dashboard/knowledge-bases"
              className="text-indigo-600 hover:underline"
            >
              Conhecimento
            </Link>
            .
          </p>
          <Link
            href="/dashboard/knowledge-bases"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-xs font-medium rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Criar base de conhecimento
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {kbs.map((kb) => {
            const conn = getConnection(kb.id);
            const connected = !!conn;
            const inactive = conn && !conn.is_active;
            const isBusy = busy[kb.id] ?? false;
            const err = actionErrors[kb.id];
            const writeAllowed = canWrite(role);

            return (
              <div
                key={kb.id}
                className="flex items-center gap-3 p-4 bg-white rounded-xl border border-gray-200 hover:border-gray-300 transition-colors"
              >
                {/* Icon */}
                <div
                  className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
                    connected ? "bg-indigo-50 border border-indigo-100" : "bg-gray-50 border border-gray-200"
                  }`}
                >
                  <BookOpen
                    className={`w-4.5 h-4.5 ${connected ? "text-indigo-500" : "text-gray-400"}`}
                  />
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-gray-900 truncate">{kb.name}</span>
                    {connected && !inactive && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-200">
                        <Check className="w-3 h-3" />
                        Conectada
                      </span>
                    )}
                    {inactive && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
                        Inativa
                      </span>
                    )}
                    <KbStatusBadge status={kb.status} />
                  </div>
                  {kb.description && (
                    <p className="text-xs text-gray-500 truncate mt-0.5">{kb.description}</p>
                  )}
                  {err && <p className="text-xs text-red-500 mt-0.5">{err}</p>}
                </div>

                {/* Action — only write roles can connect/disconnect */}
                {writeAllowed && (
                  isBusy ? (
                    <Loader2 className="w-4 h-4 text-gray-400 animate-spin flex-shrink-0" />
                  ) : connected ? (
                    <button
                      type="button"
                      onClick={() => handleDisconnect(kb.id)}
                      title="Desconectar base"
                      className="flex-shrink-0 flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-red-50 hover:text-red-600 hover:border-red-200 transition-colors"
                    >
                      <Minus className="w-3.5 h-3.5" />
                      Desconectar
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleConnect(kb.id)}
                      title="Conectar base"
                      className="flex-shrink-0 flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-colors"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Conectar
                    </button>
                  )
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Link to manage KBs */}
      {kbs.length > 0 && (
        <div className="flex justify-end">
          <Link
            href="/dashboard/knowledge-bases"
            className="text-xs text-indigo-600 hover:underline"
          >
            Gerenciar bases de conhecimento →
          </Link>
        </div>
      )}
    </div>
  );
}

