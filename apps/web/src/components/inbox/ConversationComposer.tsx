"use client";

import { useRef, useState } from "react";
import { api } from "@/lib/api";
import type { MemberRole, MessageDirection, MessageSenderType } from "@/lib/api";

type Mode = "human" | "customer";

const MODES: { value: Mode; label: string; direction: MessageDirection; senderType: MessageSenderType; placeholder: string }[] = [
  { value: "human",    label: "Responder como humano", direction: "outbound", senderType: "human",    placeholder: "Escreva sua resposta…" },
  { value: "customer", label: "Simular cliente",        direction: "inbound",  senderType: "customer", placeholder: "Simule uma mensagem do cliente…" },
];

function canSend(role: MemberRole | null): boolean {
  return role === "owner" || role === "admin" || role === "member";
}

function ArchivedBanner() {
  return (
    <div className="px-5 py-3 border-t border-nb-border bg-nb-surface flex-shrink-0">
      <p className="text-xs text-nb-muted text-center">Esta conversa está arquivada.</p>
    </div>
  );
}

function ViewerBanner() {
  return (
    <div className="px-5 py-3 border-t border-nb-border bg-nb-surface flex-shrink-0">
      <p className="text-xs text-nb-muted text-center">Você tem permissão apenas para visualizar esta conversa.</p>
    </div>
  );
}

export function ConversationComposer({
  conversationId,
  conversationStatus,
  userRole,
  onSent,
}: {
  conversationId: string;
  conversationStatus: string;
  userRole: MemberRole | null;
  onSent: () => void;
}) {
  const [mode, setMode] = useState<Mode>("human");
  const [content, setContent] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  if (conversationStatus === "archived") return <ArchivedBanner />;
  if (!canSend(userRole)) return <ViewerBanner />;

  const activeModeConfig = MODES.find((m) => m.value === mode)!;
  const trimmed = content.trim();

  const handleSend = async () => {
    if (!trimmed || sending) return;
    setSending(true);
    setSendError(null);
    try {
      await api.conversations.messages.create(conversationId, {
        content: trimmed,
        direction: activeModeConfig.direction,
        sender_type: activeModeConfig.senderType,
      });
      setContent("");
      onSent();
      textareaRef.current?.focus();
    } catch (e) {
      setSendError(e instanceof Error ? e.message : "Erro ao enviar mensagem.");
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); void handleSend(); }
  };

  return (
    <div className="flex flex-col border-t border-nb-border bg-nb-surface flex-shrink-0">
      <div className="flex items-center gap-1 px-4 pt-3 pb-2">
        {MODES.map((m) => (
          <button
            key={m.value}
            type="button"
            onClick={() => setMode(m.value)}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
              mode === m.value
                ? m.value === "customer"
                  ? "bg-nb-soft text-nb-secondary"
                  : "bg-nb-primary-bg text-nb-primary-strong"
                : "text-nb-muted hover:text-nb-secondary"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="px-4 pb-4 flex flex-col gap-2">
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={activeModeConfig.placeholder}
          rows={3}
          disabled={sending}
          className="w-full resize-none rounded-xl border border-nb-border bg-nb-elevated px-3 py-2.5 text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 disabled:opacity-50 transition-colors"
        />

        {sendError && <p className="text-xs text-nb-danger">{sendError}</p>}

        <div className="flex items-center justify-between">
          <p className="text-[10px] text-nb-muted">
            {mode === "customer" ? "Simulação para testes internos" : "⌘ + Enter para enviar"}
          </p>
          <button
            type="button"
            onClick={() => void handleSend()}
            disabled={!trimmed || sending}
            className="px-4 py-1.5 rounded-xl text-xs font-medium bg-nb-primary text-white hover:bg-nb-primary-strong disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {sending ? "Enviando…" : "Enviar"}
          </button>
        </div>
      </div>
    </div>
  );
}
