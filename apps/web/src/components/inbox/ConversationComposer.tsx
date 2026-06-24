"use client";

import { useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api";
import type { MemberRole, MessageDirection, MessageSenderType } from "@/lib/api";

// ── Mode config ───────────────────────────────────────────────────────────────

type Mode = "human" | "customer";

const MODES: { value: Mode; label: string; direction: MessageDirection; senderType: MessageSenderType; placeholder: string }[] = [
  {
    value:      "human",
    label:      "Responder como humano",
    direction:  "outbound",
    senderType: "human",
    placeholder:"Escreva sua resposta…",
  },
  {
    value:      "customer",
    label:      "Simular cliente",
    direction:  "inbound",
    senderType: "customer",
    placeholder:"Simule uma mensagem do cliente…",
  },
];

// ── RBAC helpers ──────────────────────────────────────────────────────────────

function canSend(role: MemberRole | null): boolean {
  return role === "owner" || role === "admin" || role === "member";
}

// ── Blocked states ────────────────────────────────────────────────────────────

function ArchivedBanner() {
  return (
    <div className="px-5 py-3 border-t border-gray-800 bg-gray-900/60 flex-shrink-0">
      <p className="text-xs text-gray-500 text-center">Esta conversa está arquivada.</p>
    </div>
  );
}

function ViewerBanner() {
  return (
    <div className="px-5 py-3 border-t border-gray-800 bg-gray-900/60 flex-shrink-0">
      <p className="text-xs text-gray-500 text-center">
        Você tem permissão apenas para visualizar esta conversa.
      </p>
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

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
  const { getToken } = useAuth();
  const [mode, setMode] = useState<Mode>("human");
  const [content, setContent] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Blocked states — render before the form
  if (conversationStatus === "archived") return <ArchivedBanner />;
  if (!canSend(userRole)) return <ViewerBanner />;

  const activeModeConfig = MODES.find((m) => m.value === mode)!;
  const trimmed = content.trim();

  const handleSend = async () => {
    if (!trimmed || sending) return;
    setSending(true);
    setSendError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada. Recarregue a página.");
      await api.conversations.messages.create(token, conversationId, {
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
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      void handleSend();
    }
  };

  return (
    <div className="flex flex-col border-t border-gray-800 bg-gray-900/60 flex-shrink-0">
      {/* Mode segmented control */}
      <div className="flex items-center gap-1 px-4 pt-3 pb-2">
        {MODES.map((m) => (
          <button
            key={m.value}
            type="button"
            onClick={() => setMode(m.value)}
            className={`
              px-2.5 py-1 rounded text-xs font-medium transition-colors
              ${mode === m.value
                ? m.value === "customer"
                  ? "bg-gray-700 text-gray-200"
                  : "bg-indigo-600/25 text-indigo-300"
                : "text-gray-500 hover:text-gray-400"}
            `}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Textarea + send */}
      <div className="px-4 pb-4 flex flex-col gap-2">
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={activeModeConfig.placeholder}
          rows={3}
          disabled={sending}
          className="
            w-full resize-none rounded-lg border border-gray-700 bg-gray-800 px-3 py-2.5
            text-sm text-gray-100 placeholder-gray-600
            focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/40
            disabled:opacity-50 transition-colors
          "
        />

        {sendError && (
          <p className="text-xs text-red-400">{sendError}</p>
        )}

        <div className="flex items-center justify-between">
          <p className="text-[10px] text-gray-600">
            {mode === "customer" ? "Simulação para testes internos" : "⌘ + Enter para enviar"}
          </p>
          <button
            type="button"
            onClick={() => void handleSend()}
            disabled={!trimmed || sending}
            className="
              px-4 py-1.5 rounded-lg text-xs font-medium transition-colors
              bg-indigo-600 text-white
              hover:bg-indigo-500
              disabled:opacity-40 disabled:cursor-not-allowed
            "
          >
            {sending ? "Enviando…" : "Enviar"}
          </button>
        </div>
      </div>
    </div>
  );
}
