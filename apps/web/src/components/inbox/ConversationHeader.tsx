"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Check, Hand, KanbanSquare, Loader2, UserCheck, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Conversation, ConversationStatus, MemberRole, Pipeline, PipelineStage } from "@/lib/api";

// Small, quiet badge — only renders when this conversation actually had a
// tool call fail (or a run crash outright). Links straight to that run,
// pre-filtered, in the Execuções screen — no need to dig through the
// transcript or ask an engineer to check the database.
function AgentErrorIndicator({ conversationId }: { conversationId: string }) {
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setHasError(false);
    api.agentRuns
      .list({ conversation_id: conversationId, had_error: true, limit: 1 })
      .then((runs) => { if (!cancelled) setHasError(runs.length > 0); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [conversationId]);

  if (!hasError) return null;

  return (
    <Link
      href={`/dashboard/logs?conversation_id=${conversationId}`}
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-medium bg-nb-danger/10 border border-nb-danger/20 text-nb-danger flex-shrink-0 hover:opacity-80 transition-opacity"
      title="Uma ferramenta falhou nessa conversa — ver detalhes"
    >
      <AlertTriangle className="w-3 h-3" />
      Falha detectada
    </Link>
  );
}

// ── SendToPipelineModal ───────────────────────────────────────────────────────

function SendToPipelineModal({
  conversationId,
  onClose,
  onSuccess,
}: {
  conversationId: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [selectedPipelineId, setSelectedPipelineId] = useState("");
  const [selectedStageId, setSelectedStageId] = useState("");
  const [loadingPipelines, setLoadingPipelines] = useState(true);
  const [loadingStages, setLoadingStages] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    async function fetchPipelines() {
      setLoadingPipelines(true);
      try {
        const list = await api.pipelines.list();
        setPipelines(list);
        if (list.length > 0) {
          setSelectedPipelineId(list[0].id);
        }
      } catch {
        setError("Erro ao carregar pipelines.");
      } finally {
        setLoadingPipelines(false);
      }
    }
    void fetchPipelines();
  }, []);

  useEffect(() => {
    if (!selectedPipelineId) { setStages([]); setSelectedStageId(""); return; }
    setLoadingStages(true);
    setSelectedStageId("");
    api.pipelines.stages.list(selectedPipelineId)
      .then((list) => {
        const sorted = [...list].sort((a, b) => a.position - b.position);
        setStages(sorted);
        if (sorted.length > 0) setSelectedStageId(sorted[0].id);
      })
      .catch(() => setError("Erro ao carregar etapas."))
      .finally(() => setLoadingStages(false));
  }, [selectedPipelineId]);

  async function handleConfirm() {
    if (!selectedPipelineId || !selectedStageId) {
      setError("Selecione um pipeline e uma etapa.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api.pipelines.entries.create(selectedPipelineId, {
        conversation_id: conversationId,
        stage_id: selectedStageId,
      });
      setSuccessMsg("Conversa enviada para o pipeline.");
      setTimeout(() => { onSuccess(); onClose(); }, 1200);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError("Esta conversa já está neste pipeline.");
      } else {
        setError("Erro ao enviar conversa para o pipeline.");
      }
    } finally {
      setSaving(false);
    }
  }

  const noPipelines = !loadingPipelines && pipelines.length === 0;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      onClick={(e) => e.target === overlayRef.current && onClose()}
    >
      <div className="w-full max-w-sm bg-nb-surface border border-nb-border rounded-2xl shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-nb-border shrink-0">
          <div className="flex items-center gap-2">
            <KanbanSquare className="w-4 h-4 text-nb-primary" />
            <h2 className="text-sm font-semibold text-nb-text">Enviar para Pipeline</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-nb-elevated text-nb-muted hover:text-nb-secondary transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-4">
          {loadingPipelines ? (
            <div className="flex justify-center py-6">
              <Loader2 className="w-5 h-5 animate-spin text-nb-muted" />
            </div>
          ) : noPipelines ? (
            <div className="text-center py-4">
              <p className="text-xs text-nb-muted mb-3">
                Nenhum pipeline disponível. Crie um pipeline primeiro.
              </p>
              <a
                href="/dashboard/pipeline"
                className="text-xs text-nb-primary hover:underline font-medium"
              >
                Ir para Pipelines →
              </a>
            </div>
          ) : (
            <>
              <div>
                <label className="block text-xs font-medium text-nb-secondary mb-1.5">Pipeline</label>
                <select
                  className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text focus:outline-none focus:border-nb-primary transition-colors"
                  value={selectedPipelineId}
                  onChange={(e) => setSelectedPipelineId(e.target.value)}
                  disabled={saving}
                >
                  {pipelines.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-nb-secondary mb-1.5">Etapa</label>
                {loadingStages ? (
                  <div className="flex items-center gap-2 py-2">
                    <Loader2 className="w-4 h-4 animate-spin text-nb-muted" />
                    <span className="text-xs text-nb-muted">Carregando etapas…</span>
                  </div>
                ) : (
                  <select
                    className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text focus:outline-none focus:border-nb-primary transition-colors disabled:opacity-50"
                    value={selectedStageId}
                    onChange={(e) => setSelectedStageId(e.target.value)}
                    disabled={saving || stages.length === 0}
                  >
                    {stages.length === 0 ? (
                      <option value="">Nenhuma etapa disponível</option>
                    ) : (
                      stages.map((s) => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                      ))
                    )}
                  </select>
                )}
              </div>
            </>
          )}

          {error && <p className="text-xs text-nb-danger">{error}</p>}
          {successMsg && <p className="text-xs text-green-600">{successMsg}</p>}
        </div>

        {/* Footer */}
        {!noPipelines && !loadingPipelines && (
          <div className="flex justify-end gap-2 px-5 pb-4 shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => { void handleConfirm(); }}
              disabled={saving || !selectedStageId || !!successMsg}
              className="px-4 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong disabled:opacity-40 transition-colors"
            >
              {saving ? "Enviando…" : "Enviar"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

const CHANNEL_LABELS: Record<string, string> = {
  internal:   "Internal",
  web_widget: "Widget",
  whatsapp:   "WhatsApp",
  instagram:  "Instagram",
  email:      "E-mail",
  api:        "API",
};

const STATUS_OPTIONS: { value: ConversationStatus; label: string }[] = [
  { value: "open",     label: "Aberta"    },
  { value: "pending",  label: "Pendente"  },
  { value: "resolved", label: "Resolvida" },
  { value: "archived", label: "Arquivada" },
];

function canWrite(role: MemberRole | null) {
  return role === "owner" || role === "admin" || role === "member";
}

export function ConversationHeader({
  conversation,
  userRole,
  onUpdate,
}: {
  conversation: Conversation;
  userRole: MemberRole | null;
  onUpdate: (updated: Conversation) => void;
}) {
  const [patching, setPatching] = useState(false);
  const [patchError, setPatchError] = useState<string | null>(null);
  const [sendToPipelineOpen, setSendToPipelineOpen] = useState(false);

  const writable = canWrite(userRole) && !patching;

  const patch = async (data: { status?: ConversationStatus; ai_enabled?: boolean }) => {
    setPatchError(null);
    setPatching(true);
    try {
      const updated = await api.conversations.update(conversation.id, data);
      onUpdate(updated);
    } catch {
      setPatchError("Não foi possível atualizar a conversa.");
    } finally {
      setPatching(false);
    }
  };

  const handleStatusChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    void patch({ status: e.target.value as ConversationStatus });
  };

  const handleTakeOver = async () => {
    setPatchError(null);
    setPatching(true);
    try {
      const updated = await api.conversations.takeOver(conversation.id);
      onUpdate(updated);
    } catch {
      setPatchError("Não foi possível assumir a conversa.");
    } finally {
      setPatching(false);
    }
  };

  const handleReturnToAI = async () => {
    setPatchError(null);
    setPatching(true);
    try {
      const updated = await api.conversations.returnToAI(conversation.id);
      onUpdate(updated);
    } catch {
      setPatchError("Não foi possível devolver para a IA.");
    } finally {
      setPatching(false);
    }
  };

  const channelLabel = CHANNEL_LABELS[conversation.channel_type] ?? conversation.channel_type;

  // Determine the AI/human ownership state for UI rendering.
  const isHumanAssigned = conversation.assigned_user_id !== null;
  const isAIPaused = !conversation.ai_enabled;

  // Show "Assumir" only in the limbo state: AI paused and no human assigned.
  // When AI is active, the composer banner already provides this action.
  const showTakeOver = !isHumanAssigned && isAIPaused;
  // Show "Devolver para IA" when human is assigned or AI is paused.
  const showReturnToAI = isHumanAssigned || isAIPaused;

  return (
    <div className="border-b border-nb-border flex-shrink-0">
      <div className="flex items-center gap-3 px-5 py-3 min-w-0 flex-wrap gap-y-2">
        <span className="text-sm font-semibold text-nb-text truncate max-w-[180px]">
          {conversation.contact_name ?? "Contato sem nome"}
        </span>

        <span className="inline-flex items-center px-2 py-0.5 rounded-lg text-[10px] font-medium bg-nb-elevated border border-nb-border text-nb-muted flex-shrink-0">
          {channelLabel}
        </span>

        {/* AI / human ownership badge */}
        {isHumanAssigned ? (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-medium bg-nb-warning/10 border border-nb-warning/20 text-nb-warning flex-shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-nb-warning flex-shrink-0" />
            Atendimento humano
          </span>
        ) : isAIPaused ? (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-medium bg-nb-elevated border border-nb-border text-nb-muted flex-shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-nb-border-strong flex-shrink-0" />
            IA pausada
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-medium bg-nb-primary-bg border border-nb-primary/20 text-nb-primary-strong flex-shrink-0">
            <span className={`w-1.5 h-1.5 rounded-full bg-nb-primary flex-shrink-0 ${patching ? "animate-pulse" : ""}`} />
            IA ativa
          </span>
        )}

        <AgentErrorIndicator conversationId={conversation.id} />

        <div className="flex-1 min-w-0" />

        <button
          type="button"
          onClick={() => setSendToPipelineOpen(true)}
          title="Enviar para Pipeline"
          aria-label="Enviar para Pipeline"
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-medium transition-colors flex-shrink-0 bg-nb-elevated text-nb-secondary hover:bg-nb-soft border border-nb-border"
        >
          <KanbanSquare className="w-3 h-3" />
          Enviar para Pipeline
        </button>

        <select
          value={conversation.status}
          onChange={handleStatusChange}
          disabled={!writable}
          aria-label="Alterar status da conversa"
          className="bg-nb-elevated border border-nb-border text-nb-secondary text-xs rounded-xl px-2 py-1 focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer flex-shrink-0"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>

        {/* Take-over / Return to AI control */}
        {showReturnToAI ? (
          <button
            type="button"
            onClick={() => { void handleReturnToAI(); }}
            disabled={!writable}
            title="Remove o responsável humano e reativa as respostas automáticas."
            aria-label="Devolver para IA"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-medium transition-colors flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed bg-nb-primary-bg text-nb-primary-strong hover:bg-nb-primary/25"
          >
            Devolver para IA
          </button>
        ) : showTakeOver ? (
          <button
            type="button"
            onClick={() => { void handleTakeOver(); }}
            disabled={!writable}
            title="Pausa a IA e atribui esta conversa a você."
            aria-label="Assumir conversa"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-medium transition-colors flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed bg-nb-elevated text-nb-secondary hover:bg-nb-soft border border-nb-border"
          >
            Assumir
          </button>
        ) : null}
      </div>

      {/* Handoff reason row — only for the "IA pausada" limbo state (auto-paused
          by the "Solicitar humano" tool), distinct from a manual "Assumir" take-over. */}
      {isAIPaused && !isHumanAssigned && conversation.handoff_reason && (
        <div className="flex items-center gap-1.5 px-5 pb-2">
          <Hand className="w-3 h-3 text-nb-muted flex-shrink-0" />
          <span className="text-[10px] text-nb-muted truncate">
            {conversation.handoff_reason}
          </span>
        </div>
      )}

      {/* Assignment reason row — set by the "Atribuir a um operador" tool. Only
          while a human is assigned; distinct from the handoff_reason row above,
          which only ever shows in the pre-assignment "IA pausada" limbo state. */}
      {isHumanAssigned && conversation.assignment_reason && (
        <div className="flex items-center gap-1.5 px-5 pb-2">
          <UserCheck className="w-3 h-3 text-nb-muted flex-shrink-0" />
          <span className="text-[10px] text-nb-muted truncate">
            {conversation.assignment_reason}
          </span>
        </div>
      )}

      {/* Resolution summary row — set by the "Marcar como resolvido" tool. */}
      {conversation.status === "resolved" && conversation.resolution_summary && (
        <div className="flex items-center gap-1.5 px-5 pb-2">
          <Check className="w-3 h-3 text-nb-muted flex-shrink-0" />
          <span className="text-[10px] text-nb-muted truncate">
            {conversation.resolution_summary}
          </span>
        </div>
      )}

      {/* Attribution row — shown for web_widget conversations with source data */}
      {conversation.channel_type === "web_widget" && (
        conversation.source_page_title || conversation.source_page_url || conversation.utm_source
      ) && (
        <div className="flex items-center gap-2 px-5 pb-2 flex-wrap">
          {(conversation.source_page_title || conversation.source_page_url) && (
            <span className="text-[10px] text-nb-muted truncate max-w-[200px]" title={conversation.source_page_url ?? undefined}>
              📄 {conversation.source_page_title || (() => {
                try { return new URL(conversation.source_page_url!).hostname; } catch { return conversation.source_page_url; }
              })()}
            </span>
          )}
          {conversation.utm_source && (
            <span className="text-[10px] text-nb-muted">
              {[conversation.utm_source, conversation.utm_medium, conversation.utm_campaign]
                .filter(Boolean)
                .join(" / ")}
            </span>
          )}
        </div>
      )}

      {patchError && (
        <div className="px-5 pb-2">
          <p className="text-[10px] text-nb-danger">{patchError}</p>
        </div>
      )}

      {sendToPipelineOpen && (
        <SendToPipelineModal
          conversationId={conversation.id}
          onClose={() => setSendToPipelineOpen(false)}
          onSuccess={() => {}}
        />
      )}
    </div>
  );
}
