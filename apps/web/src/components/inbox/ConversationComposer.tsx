"use client";

import { useRef, useState } from "react";
import { api } from "@/lib/api";
import type { MemberRole } from "@/lib/api";

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

function AIActiveBanner({ onTakeOver, taking }: { onTakeOver: () => void; taking: boolean }) {
  return (
    <div className="px-5 py-4 border-t border-nb-border bg-nb-surface flex-shrink-0 flex flex-col gap-3">
      <div className="flex items-start gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-nb-primary mt-[5px] flex-shrink-0" />
        <p className="text-xs text-nb-secondary leading-relaxed">
          A IA está respondendo automaticamente esta conversa. Para enviar uma resposta manual, assuma a conversa.
        </p>
      </div>
      <button
        type="button"
        onClick={onTakeOver}
        disabled={taking}
        className="self-start px-3 py-1.5 rounded-xl text-xs font-medium bg-nb-elevated text-nb-secondary hover:bg-nb-soft border border-nb-border disabled:opacity-50 transition-colors"
      >
        {taking ? "Assumindo…" : "Assumir conversa"}
      </button>
    </div>
  );
}

export function ConversationComposer({
  conversationId,
  conversationStatus,
  aiEnabled,
  userRole,
  onSent,
  onTakeOver,
}: {
  conversationId: string;
  conversationStatus: string;
  aiEnabled: boolean;
  userRole: MemberRole | null;
  onSent: () => void;
  onTakeOver: () => Promise<void>;
}) {
  const [content, setContent] = useState("");
  const [sending, setSending] = useState(false);
  const [taking, setTaking] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  if (conversationStatus === "archived") return <ArchivedBanner />;
  if (!canSend(userRole)) return <ViewerBanner />;

  if (aiEnabled) {
    const handleTakeOver = async () => {
      setTaking(true);
      try { await onTakeOver(); } finally { setTaking(false); }
    };
    return <AIActiveBanner onTakeOver={() => void handleTakeOver()} taking={taking} />;
  }

  const trimmed = content.trim();

  const handleSend = async () => {
    if (!trimmed || sending) return;
    setSending(true);
    setSendError(null);
    try {
      await api.conversations.messages.create(conversationId, {
        content: trimmed,
        direction: "outbound",
        sender_type: "human",
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
      <div className="px-4 pt-3 pb-1">
        <span className="text-xs font-medium text-nb-primary-strong">Responder como humano</span>
      </div>

      <div className="px-4 pb-4 flex flex-col gap-2">
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Escreva sua resposta…"
          rows={3}
          disabled={sending}
          className="w-full resize-none rounded-xl border border-nb-border bg-nb-elevated px-3 py-2.5 text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 disabled:opacity-50 transition-colors"
        />

        {sendError && <p className="text-xs text-nb-danger">{sendError}</p>}

        <div className="flex items-center justify-between">
          <p className="text-[10px] text-nb-muted">⌘ + Enter para enviar</p>
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
