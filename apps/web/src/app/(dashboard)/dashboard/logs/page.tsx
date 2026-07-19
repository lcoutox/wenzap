"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Loader2,
  MinusCircle,
  RefreshCw,
  X,
  XCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Agent, AgentRun, AgentRunDetail, AgentRunToolCall } from "@/lib/api";
import { inputCls } from "@/components/agents/workspace/AgentHeader";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

function formatJson(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "string") {
    try {
      return JSON.stringify(JSON.parse(value), null, 2);
    } catch {
      return value;
    }
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

// A run is "clean" only when the turn completed AND no tool inside it failed.
function runOutcome(run: AgentRun): "clean" | "tool_error" | "failed" | "other" {
  if (run.status === "failed") return "failed";
  if (run.status === "success" && run.had_tool_error) return "tool_error";
  if (run.status === "success") return "clean";
  return "other";
}

function StatusBadge({ run }: { run: AgentRun }) {
  const outcome = runOutcome(run);
  const map = {
    clean: { icon: CheckCircle2, label: "OK", cls: "text-nb-success bg-nb-success/10" },
    tool_error: { icon: AlertTriangle, label: "Tool falhou", cls: "text-amber-500 bg-amber-500/10" },
    failed: { icon: XCircle, label: "Falhou", cls: "text-nb-danger bg-nb-danger/10" },
    other: { icon: MinusCircle, label: run.status, cls: "text-nb-muted bg-nb-elevated" },
  }[outcome];
  const Icon = map.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${map.cls}`}>
      <Icon className="w-3 h-3" /> {map.label}
    </span>
  );
}

function ToolCallStatusBadge({ status }: { status: string | null }) {
  if (status === "error") {
    return <span className="text-[11px] font-medium text-nb-danger">erro</span>;
  }
  return <span className="text-[11px] font-medium text-nb-success">sucesso</span>;
}

// ── Detail modal ─────────────────────────────────────────────────────────────

function RunDetailModal({ runId, onClose }: { runId: string; onClose: () => void }) {
  const [detail, setDetail] = useState<AgentRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.agentRuns.get(runId)
      .then(setDetail)
      .catch(() => setError("Não foi possível carregar essa execução."))
      .finally(() => setLoading(false));
  }, [runId]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full max-w-2xl bg-nb-surface border border-nb-border rounded-2xl shadow-2xl flex flex-col max-h-[85vh]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-nb-border shrink-0">
          <h2 className="text-sm font-semibold text-nb-text">Detalhe da execução</h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-nb-elevated text-nb-muted hover:text-nb-secondary transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="overflow-y-auto flex-1 px-5 py-4 space-y-4">
          {loading && (
            <div className="flex items-center justify-center py-10 text-nb-muted">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
          )}
          {error && <p className="text-xs text-nb-danger">{error}</p>}
          {detail && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge run={detail} />
                <span className="text-xs text-nb-muted">{formatDateTime(detail.created_at)}</span>
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <p className="text-nb-muted">Contato</p>
                  <p className="text-nb-text">{detail.contact_name || detail.contact_phone || "—"}</p>
                </div>
                <div>
                  <p className="text-nb-muted">Agente</p>
                  <p className="text-nb-text">{detail.agent_name || "—"}</p>
                </div>
                <div>
                  <p className="text-nb-muted">Créditos usados</p>
                  <p className="text-nb-text">{detail.credits_used}</p>
                </div>
                <div>
                  <p className="text-nb-muted">Duração</p>
                  <p className="text-nb-text">{detail.duration_ms != null ? `${detail.duration_ms}ms` : "—"}</p>
                </div>
              </div>
              {detail.error_message && (
                <div className="p-2.5 bg-nb-danger/10 border border-nb-danger/20 rounded-xl text-xs text-nb-danger">
                  {detail.error_message}
                </div>
              )}
              <Link
                href={`/dashboard/inbox?conv=${detail.conversation_id}`}
                className="inline-flex items-center gap-1 text-xs font-medium text-nb-primary hover:underline"
              >
                Ver conversa <ChevronRight className="w-3 h-3" />
              </Link>

              <div>
                <p className="text-xs font-medium text-nb-secondary mb-2">
                  Ferramentas chamadas {detail.tool_calls.length === 0 && "— nenhuma"}
                </p>
                <div className="space-y-2">
                  {detail.tool_calls.map((tc: AgentRunToolCall, i: number) => (
                    <div key={i} className="p-3 bg-nb-panel border border-nb-border rounded-xl space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono font-medium text-nb-text">{tc.tool_name}</span>
                        <ToolCallStatusBadge status={tc.status} />
                      </div>
                      <div>
                        <p className="text-[11px] text-nb-muted mb-0.5">Entrada</p>
                        <pre className="text-[11px] font-mono text-nb-secondary bg-nb-bg rounded-lg p-2 overflow-x-auto whitespace-pre-wrap break-all">
                          {formatJson(tc.input)}
                        </pre>
                      </div>
                      <div>
                        <p className="text-[11px] text-nb-muted mb-0.5">Saída</p>
                        <pre className="text-[11px] font-mono text-nb-secondary bg-nb-bg rounded-lg p-2 overflow-x-auto whitespace-pre-wrap break-all">
                          {formatJson(tc.output)}
                        </pre>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function LogsPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const hadErrorOnly = searchParams.get("had_error") === "true";
  const agentId = searchParams.get("agent_id") || "";
  const toolName = searchParams.get("tool_name") || "";
  const conversationId = searchParams.get("conversation_id") || "";

  function setFilter(key: string, value: string | null) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value);
    else params.delete(key);
    router.push(`/dashboard/logs?${params.toString()}`);
  }

  const refresh = useCallback(() => {
    setLoading(true);
    setLoadError(null);
    api.agentRuns
      .list({
        had_error: hadErrorOnly || undefined,
        agent_id: agentId || undefined,
        tool_name: toolName || undefined,
        conversation_id: conversationId || undefined,
        limit: 100,
      })
      .then(setRuns)
      .catch(() => setLoadError("Não foi possível carregar as execuções."))
      .finally(() => setLoading(false));
  }, [hadErrorOnly, agentId, toolName, conversationId]);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { api.agents.list().then(setAgents).catch(() => setAgents([])); }, []);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-nb-text">Execuções</h1>
          <p className="text-xs text-nb-muted mt-0.5">
            Todo turno que seu agente rodou — o que ele respondeu e quais ferramentas chamou, com sucesso ou não.
          </p>
        </div>
        <button
          type="button"
          onClick={refresh}
          className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Atualizar
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setFilter("had_error", hadErrorOnly ? null : "true")}
          className={`px-3 py-1.5 text-xs font-medium rounded-xl border transition-colors ${
            hadErrorOnly
              ? "bg-nb-danger/10 border-nb-danger/30 text-nb-danger"
              : "border-nb-border text-nb-secondary hover:bg-nb-elevated"
          }`}
        >
          Só falhas
        </button>
        <select
          value={agentId}
          onChange={(e) => setFilter("agent_id", e.target.value || null)}
          className={`${inputCls} w-auto`}
        >
          <option value="">Todos os agentes</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>
        <input
          type="text"
          value={toolName}
          onChange={(e) => setFilter("tool_name", e.target.value || null)}
          placeholder="Nome da ferramenta"
          className={`${inputCls} w-auto font-mono text-xs`}
        />
        {conversationId && (
          <button
            type="button"
            onClick={() => setFilter("conversation_id", null)}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-nb-primary border border-nb-primary/30 rounded-xl bg-nb-primary/10"
          >
            Conversa específica <X className="w-3 h-3" />
          </button>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-nb-muted">
          <Loader2 className="w-5 h-5 animate-spin" />
        </div>
      ) : loadError ? (
        <p className="text-xs text-nb-danger">{loadError}</p>
      ) : runs.length === 0 ? (
        <div className="text-center py-16 text-nb-muted text-sm">Nenhuma execução encontrada.</div>
      ) : (
        <div className="border border-nb-border rounded-2xl overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-nb-panel text-nb-muted">
              <tr>
                <th className="text-left font-medium px-4 py-2.5">Quando</th>
                <th className="text-left font-medium px-4 py-2.5">Contato</th>
                <th className="text-left font-medium px-4 py-2.5">Agente</th>
                <th className="text-left font-medium px-4 py-2.5">Ferramentas</th>
                <th className="text-left font-medium px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.id}
                  onClick={() => setSelectedRunId(run.id)}
                  className="border-t border-nb-border hover:bg-nb-elevated transition-colors cursor-pointer"
                >
                  <td className="px-4 py-2.5 text-nb-secondary whitespace-nowrap">
                    {formatDateTime(run.created_at)}
                  </td>
                  <td className="px-4 py-2.5 text-nb-text">
                    {run.contact_name || run.contact_phone || "—"}
                  </td>
                  <td className="px-4 py-2.5 text-nb-secondary">{run.agent_name || "—"}</td>
                  <td className="px-4 py-2.5 text-nb-muted font-mono">
                    {run.tool_names.length > 0 ? run.tool_names.join(", ") : "—"}
                  </td>
                  <td className="px-4 py-2.5"><StatusBadge run={run} /></td>
                  <td className="px-4 py-2.5 text-nb-muted"><ChevronRight className="w-3.5 h-3.5" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedRunId && (
        <RunDetailModal runId={selectedRunId} onClose={() => setSelectedRunId(null)} />
      )}
    </div>
  );
}

export default function LogsPage() {
  return (
    <Suspense fallback={null}>
      <LogsPageInner />
    </Suspense>
  );
}
