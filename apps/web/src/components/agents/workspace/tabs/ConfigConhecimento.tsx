"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BookOpen, Check, Info, Loader2, Minus, Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { AgentKnowledgeBase, KnowledgeBase, MemberRole } from "@/lib/api";

function canWrite(role: MemberRole | null) {
  return role === "owner" || role === "admin" || role === "member";
}

function KbStatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    active:   { label: "Ativa",     cls: "bg-nb-success/10 text-nb-success border-nb-success/20"  },
    inactive: { label: "Inativa",   cls: "bg-nb-elevated   text-nb-muted   border-nb-border"      },
    archived: { label: "Arquivada", cls: "bg-nb-danger/10  text-nb-danger  border-nb-danger/20"   },
  };
  const s = map[status] ?? { label: status, cls: "bg-nb-elevated text-nb-muted border-nb-border" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${s.cls}`}>
      {s.label}
    </span>
  );
}

export function ConfigConhecimento({
  agentId,
  role,
}: {
  agentId: string;
  role: MemberRole | null;
}) {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [connections, setConnections] = useState<AgentKnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [actionErrors, setActionErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    (async () => {
      try {
        const [allKbs, agentKbs] = await Promise.all([
          api.knowledgeBases.list(),
          api.agents.knowledgeBases.list(agentId),
        ]);
        setKbs(allKbs);
        setConnections(agentKbs);
      } catch (e) {
        setLoadError(e instanceof Error ? e.message : "Erro ao carregar bases de conhecimento.");
      } finally {
        setLoading(false);
      }
    })();
  }, [agentId]);

  function getConnection(kbId: string): AgentKnowledgeBase | undefined {
    return connections.find((c) => c.knowledge_base_id === kbId);
  }

  async function handleConnect(kbId: string) {
    setBusy((p) => ({ ...p, [kbId]: true }));
    setActionErrors((p) => ({ ...p, [kbId]: "" }));
    try {
      const conn = await api.agents.knowledgeBases.connect(agentId, kbId);
      setConnections((prev) => {
        const existing = prev.find((c) => c.knowledge_base_id === kbId);
        if (existing) return prev.map((c) => (c.knowledge_base_id === kbId ? conn : c));
        return [...prev, conn];
      });
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        try {
          const refreshed = await api.agents.knowledgeBases.list(agentId);
          setConnections(refreshed);
        } catch { /* ignore */ }
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
      await api.agents.knowledgeBases.disconnect(agentId, kbId);
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
          <div key={i} className="h-16 bg-nb-panel rounded-2xl border border-nb-border" />
        ))}
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="p-4 bg-nb-danger/10 border border-nb-danger/20 rounded-xl text-sm text-nb-danger">
        {loadError}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-sm font-semibold text-nb-text">Conhecimento do agente</h3>
        <p className="mt-1 text-xs text-nb-muted">
          Conecte bases de conhecimento que este agente poderá usar para responder com informações da empresa.
        </p>
      </div>

      <div className="flex items-start gap-2.5 p-3 rounded-xl bg-nb-warning/10 border border-nb-warning/20">
        <Info className="w-4 h-4 text-nb-warning flex-shrink-0 mt-0.5" />
        <p className="text-xs text-nb-warning">
          As bases conectadas são usadas automaticamente pelo agente via RAG.
        </p>
      </div>

      {kbs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center border border-dashed border-nb-border rounded-2xl">
          <div className="w-12 h-12 rounded-2xl bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center mb-3">
            <BookOpen className="w-6 h-6 text-nb-primary" />
          </div>
          <p className="text-sm font-medium text-nb-secondary mb-1">
            Nenhuma base de conhecimento criada ainda.
          </p>
          <p className="text-xs text-nb-muted mb-4">
            Crie uma em{" "}
            <Link href="/dashboard/knowledge-bases" className="text-nb-primary hover:underline">
              Conhecimento
            </Link>
            .
          </p>
          <Link
            href="/dashboard/knowledge-bases"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-nb-primary text-white text-xs font-medium rounded-xl hover:bg-nb-primary-strong transition-colors"
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
                className="flex items-center gap-3 p-4 bg-nb-panel rounded-2xl border border-nb-border hover:border-nb-border-strong transition-colors"
              >
                <div
                  className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${
                    connected ? "bg-nb-primary-bg border border-nb-primary/20" : "bg-nb-elevated border border-nb-border"
                  }`}
                >
                  <BookOpen className={`w-4 h-4 ${connected ? "text-nb-primary-strong" : "text-nb-muted"}`} />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-nb-text truncate">{kb.name}</span>
                    {connected && !inactive && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-nb-success/10 text-nb-success border border-nb-success/20">
                        <Check className="w-3 h-3" />
                        Conectada
                      </span>
                    )}
                    {inactive && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-nb-warning/10 text-nb-warning border border-nb-warning/20">
                        Inativa
                      </span>
                    )}
                    <KbStatusBadge status={kb.status} />
                  </div>
                  {kb.description && (
                    <p className="text-xs text-nb-muted truncate mt-0.5">{kb.description}</p>
                  )}
                  {err && <p className="text-xs text-nb-danger mt-0.5">{err}</p>}
                </div>

                {writeAllowed && (
                  isBusy ? (
                    <Loader2 className="w-4 h-4 text-nb-muted animate-spin flex-shrink-0" />
                  ) : connected ? (
                    <button
                      type="button"
                      onClick={() => handleDisconnect(kb.id)}
                      className="flex-shrink-0 flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-danger/10 hover:text-nb-danger hover:border-nb-danger/20 transition-colors"
                    >
                      <Minus className="w-3.5 h-3.5" />
                      Desconectar
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleConnect(kb.id)}
                      className="flex-shrink-0 flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary-bg transition-colors"
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

      {kbs.length > 0 && (
        <div className="flex justify-end">
          <Link href="/dashboard/knowledge-bases" className="text-xs text-nb-primary hover:underline">
            Gerenciar bases de conhecimento →
          </Link>
        </div>
      )}
    </div>
  );
}
