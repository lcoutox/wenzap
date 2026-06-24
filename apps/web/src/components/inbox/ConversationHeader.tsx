"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api";
import type { Conversation, ConversationStatus, MemberRole } from "@/lib/api";

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
  const { getToken } = useAuth();
  const [patching, setPatching] = useState(false);
  const [patchError, setPatchError] = useState<string | null>(null);

  const writable = canWrite(userRole) && !patching;

  const patch = async (data: { status?: ConversationStatus; ai_enabled?: boolean }) => {
    setPatchError(null);
    setPatching(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      const updated = await api.conversations.update(token, conversation.id, data);
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
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      const updated = await api.conversations.takeOver(token, conversation.id);
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
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      const updated = await api.conversations.returnToAI(token, conversation.id);
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

  // Show "Assumir" when AI is active or nobody is assigned.
  const showTakeOver = !isHumanAssigned || conversation.ai_enabled;
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

        <div className="flex-1 min-w-0" />

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

      {patchError && (
        <div className="px-5 pb-2">
          <p className="text-[10px] text-nb-danger">{patchError}</p>
        </div>
      )}
    </div>
  );
}
