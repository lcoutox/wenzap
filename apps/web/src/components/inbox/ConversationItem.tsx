"use client";

import type { Conversation } from "@/lib/api";

const CHANNEL_LABELS: Record<string, string> = {
  internal:   "Internal",
  web_widget: "Widget",
  whatsapp:   "WhatsApp",
  instagram:  "Instagram",
  email:      "E-mail",
  api:        "API",
};

const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  open:     { label: "Aberta",    cls: "bg-nb-success/15 text-nb-success" },
  pending:  { label: "Pendente",  cls: "bg-nb-warning/15 text-nb-warning" },
  resolved: { label: "Resolvida", cls: "bg-nb-info/15    text-nb-info"    },
  archived: { label: "Arquivada", cls: "bg-nb-elevated   text-nb-muted"   },
};

function formatTime(iso: string): string {
  const d = new Date(iso);
  const diffMin = Math.floor((Date.now() - d.getTime()) / 60_000);
  if (diffMin < 1)  return "agora";
  if (diffMin < 60) return `${diffMin}m`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24)   return `${diffH}h`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 7)    return `${diffD}d`;
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

export function ConversationItem({ conversation, isSelected, onClick }: {
  conversation: Conversation;
  isSelected: boolean;
  onClick: () => void;
}) {
  const { label: statusLabel, cls: statusCls } =
    STATUS_CONFIG[conversation.status] ?? { label: conversation.status, cls: "bg-nb-elevated text-nb-muted" };
  const channelLabel = CHANNEL_LABELS[conversation.channel_type] ?? conversation.channel_type;
  const timeIso = conversation.last_message_at ?? conversation.created_at;

  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left px-3 py-3 border-b border-nb-border/60 transition-colors border-l-2 ${
        isSelected
          ? "bg-nb-primary-bg border-l-nb-primary"
          : "hover:bg-nb-elevated border-l-transparent"
      }`}
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <span className="text-sm font-medium text-nb-text truncate leading-tight">
          {conversation.contact_name ?? "Contato sem nome"}
        </span>
        <span className="text-xs text-nb-muted flex-shrink-0 mt-0.5">{formatTime(timeIso)}</span>
      </div>
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="inline-flex items-center px-1.5 py-0.5 rounded-lg text-[10px] font-medium bg-nb-elevated text-nb-muted">
          {channelLabel}
        </span>
        <span className={`inline-flex items-center px-1.5 py-0.5 rounded-lg text-[10px] font-medium ${statusCls}`}>
          {statusLabel}
        </span>
      </div>
    </button>
  );
}
