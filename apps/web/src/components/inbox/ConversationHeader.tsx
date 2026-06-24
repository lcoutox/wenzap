"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api";
import type { Conversation, ConversationStatus, MemberRole } from "@/lib/api";

// ── Shared config ─────────────────────────────────────────────────────────────

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

// ── Component ─────────────────────────────────────────────────────────────────

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
    } catch (e) {
      setPatchError("Não foi possível atualizar a conversa.");
      console.error(e);
    } finally {
      setPatching(false);
    }
  };

  const handleStatusChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    void patch({ status: e.target.value as ConversationStatus });
  };

  const handleAiToggle = () => {
    void patch({ ai_enabled: !conversation.ai_enabled });
  };

  const channelLabel = CHANNEL_LABELS[conversation.channel_type] ?? conversation.channel_type;

  return (
    <div className="border-b border-gray-800 flex-shrink-0">
      {/* Main row */}
      <div className="flex items-center gap-3 px-5 py-3 min-w-0 flex-wrap gap-y-2">
        {/* Contact name */}
        <span className="text-sm font-semibold text-white truncate max-w-[180px]">
          {conversation.contact_name ?? "Contato sem nome"}
        </span>

        {/* Channel badge */}
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-gray-700/60 text-gray-400 flex-shrink-0">
          {channelLabel}
        </span>

        {/* Assignment */}
        <span className="text-[10px] text-gray-600 flex-shrink-0">
          {conversation.assigned_user_id ? "Atribuída" : "Não atribuída"}
        </span>

        {/* Spacer */}
        <div className="flex-1 min-w-0" />

        {/* Status select */}
        <select
          value={conversation.status}
          onChange={handleStatusChange}
          disabled={!writable}
          aria-label="Alterar status da conversa"
          className="
            bg-gray-800 border border-gray-700 text-gray-200 text-xs rounded px-2 py-1
            focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/40
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-colors cursor-pointer flex-shrink-0
          "
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* AI toggle */}
        <button
          type="button"
          onClick={handleAiToggle}
          disabled={!writable}
          aria-label={conversation.ai_enabled ? "Desativar IA" : "Ativar IA"}
          className={`
            inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-[10px] font-medium
            transition-colors flex-shrink-0
            disabled:opacity-50 disabled:cursor-not-allowed
            ${conversation.ai_enabled
              ? "bg-indigo-600/20 text-indigo-400 hover:bg-indigo-600/30"
              : "bg-gray-700/40 text-gray-500 hover:bg-gray-700/60"}
          `}
        >
          {/* Dot indicator */}
          <span
            className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
              conversation.ai_enabled ? "bg-indigo-400" : "bg-gray-600"
            } ${patching ? "animate-pulse" : ""}`}
          />
          {conversation.ai_enabled ? "IA ativa" : "IA pausada"}
        </button>
      </div>

      {/* Error row — only shown when patch fails */}
      {patchError && (
        <div className="px-5 pb-2">
          <p className="text-[10px] text-red-400">{patchError}</p>
        </div>
      )}
    </div>
  );
}
