"use client";

import type { Conversation } from "@/lib/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

const CHANNEL_LABELS: Record<string, string> = {
  internal: "Internal",
  web_widget: "Widget",
  whatsapp: "WhatsApp",
  instagram: "Instagram",
  email: "E-mail",
  api: "API",
};

const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  open:     { label: "Aberta",    cls: "bg-emerald-500/15 text-emerald-400" },
  pending:  { label: "Pendente",  cls: "bg-yellow-500/15  text-yellow-400"  },
  resolved: { label: "Resolvida", cls: "bg-blue-500/15    text-blue-400"    },
  archived: { label: "Arquivada", cls: "bg-gray-500/15    text-gray-500"    },
};

function formatTime(iso: string): string {
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1)  return "agora";
  if (diffMin < 60) return `${diffMin}m`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24)   return `${diffH}h`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 7)    return `${diffD}d`;
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

// ── Component ─────────────────────────────────────────────────────────────────

export function ConversationItem({
  conversation,
  isSelected,
  onClick,
}: {
  conversation: Conversation;
  isSelected: boolean;
  onClick: () => void;
}) {
  const { label: statusLabel, cls: statusCls } =
    STATUS_CONFIG[conversation.status] ?? { label: conversation.status, cls: "bg-gray-500/15 text-gray-400" };

  const channelLabel =
    CHANNEL_LABELS[conversation.channel_type] ?? conversation.channel_type;

  const timeIso = conversation.last_message_at ?? conversation.created_at;

  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        w-full text-left px-3 py-3 border-b border-gray-800/60 transition-colors
        ${isSelected
          ? "bg-indigo-600/10 border-l-2 border-l-indigo-500"
          : "hover:bg-gray-800/40 border-l-2 border-l-transparent"}
      `}
    >
      {/* Contact name + time */}
      <div className="flex items-start justify-between gap-2 mb-1">
        <span className="text-sm font-medium text-gray-100 truncate leading-tight">
          {conversation.contact_name ?? "Contato sem nome"}
        </span>
        <span className="text-xs text-gray-500 flex-shrink-0 mt-0.5">
          {formatTime(timeIso)}
        </span>
      </div>

      {/* Badges */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-700/60 text-gray-400">
          {channelLabel}
        </span>
        <span
          className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${statusCls}`}
        >
          {statusLabel}
        </span>
      </div>
    </button>
  );
}
