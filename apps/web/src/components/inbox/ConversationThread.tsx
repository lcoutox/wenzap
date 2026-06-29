"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";
import type { Conversation, ConversationMessage, MemberRole, MessageDelivery } from "@/lib/api";
import { MessageBubble } from "./MessageBubble";
import { ConversationComposer } from "./ConversationComposer";
import { ConversationHeader } from "./ConversationHeader";

// Merge fresh message list into current state: update delivery status on existing
// messages without replacing the whole array (prevents flicker), append new ones.
function mergeMessages(
  prev: ConversationMessage[],
  next: ConversationMessage[],
): ConversationMessage[] {
  const prevById = new Map(prev.map((m) => [m.id, m]));
  return next.map((m) => {
    const existing = prevById.get(m.id);
    // Prefer fresh data but keep shape stable to avoid unnecessary re-renders.
    return existing ? { ...existing, ...m } : m;
  });
}

function EmptyMessages() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-8">
      <p className="text-sm text-nb-muted">Nenhuma mensagem ainda.</p>
    </div>
  );
}

function ThreadSkeleton() {
  return (
    <div className="flex flex-col gap-4 p-5 animate-pulse">
      <div className="flex gap-2">
        <div className="w-6 h-6 rounded-full bg-nb-elevated flex-shrink-0" />
        <div className="space-y-1.5">
          <div className="h-2.5 bg-nb-elevated rounded w-12" />
          <div className="h-10 bg-nb-elevated rounded-2xl w-48" />
        </div>
      </div>
      <div className="flex flex-col items-end gap-1.5">
        <div className="h-2.5 bg-nb-elevated rounded w-10" />
        <div className="h-10 bg-nb-primary-bg/40 rounded-2xl w-56" />
      </div>
      <div className="flex gap-2">
        <div className="w-6 h-6 rounded-full bg-nb-elevated flex-shrink-0" />
        <div className="space-y-1.5">
          <div className="h-2.5 bg-nb-elevated rounded w-12" />
          <div className="h-16 bg-nb-elevated rounded-2xl w-64" />
        </div>
      </div>
    </div>
  );
}

function HeaderSkeleton() {
  return <div className="h-12 border-b border-nb-border flex-shrink-0 animate-pulse bg-nb-surface" />;
}

export function ConversationThread({
  conversationId,
  onMessageSent,
  onConversationUpdated,
}: {
  conversationId: string;
  onMessageSent: () => void;
  onConversationUpdated: () => void;
}) {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [userRole, setUserRole] = useState<MemberRole | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  // Scroll-to-bottom is only automatic on initial load, after the user sends,
  // or when polling brings new messages and the user was already near the bottom.
  const shouldScrollRef = useRef(false);

  function handleMessageUpdated(updated: ConversationMessage) {
    setMessages((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
  }

  const hasFailedOutbound =
    conversation?.channel_type === "whatsapp" &&
    messages.some((m) => {
      const d = m.metadata_json?.delivery as MessageDelivery | undefined;
      return m.direction === "outbound" && d?.status === "failed";
    });

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "instant" });
  }, []);

  const load = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const [conv, msgs, me] = await Promise.all([
        api.conversations.get(id),
        api.conversations.messages.list(id, { limit: 200 }),
        api.me(),
      ]);
      setConversation(conv);
      setMessages(msgs);
      setUserRole(me.role);
      shouldScrollRef.current = true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar conversa.");
    } finally {
      setLoading(false);
    }
  };

  const handleConversationUpdated = useCallback(
    (updated: Conversation) => { setConversation(updated); onConversationUpdated(); },
    [onConversationUpdated],
  );

  const handleTakeOver = useCallback(async () => {
    const updated = await api.conversations.takeOver(conversationId);
    handleConversationUpdated(updated);
  }, [conversationId, handleConversationUpdated]);

  const reloadMessages = useCallback(async () => {
    if (!conversationId) return;
    try {
      const msgs = await api.conversations.messages.list(conversationId, { limit: 200 });
      setMessages(msgs);
    } catch { /* ignore */ }
  }, [conversationId]);

  const handleSent = useCallback(async () => {
    shouldScrollRef.current = true;
    await reloadMessages();
    onMessageSent();
    scrollToBottom();
  }, [reloadMessages, onMessageSent, scrollToBottom]);

  // Initial load on conversation change.
  useEffect(() => {
    void load(conversationId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  // Scroll only when explicitly requested (initial load or after send).
  useEffect(() => {
    if (!loading && shouldScrollRef.current && messages.length > 0) {
      scrollToBottom();
      shouldScrollRef.current = false;
    }
  }, [loading, messages, scrollToBottom]);

  // Polling — silent refresh every 3 s while this conversation is open.
  useEffect(() => {
    if (loading) return;
    const poll = async () => {
      if (document.hidden) return;
      try {
        const [conv, msgs] = await Promise.all([
          api.conversations.get(conversationId),
          api.conversations.messages.list(conversationId, { limit: 200 }),
        ]);
        setConversation(conv);
        // Capture near-bottom state before updating so we can scroll after
        // new messages are rendered, without disrupting users reading history.
        const el = scrollContainerRef.current;
        const nearBottom = el
          ? el.scrollHeight - el.scrollTop - el.clientHeight < 160
          : false;
        setMessages((prev) => {
          const merged = mergeMessages(prev, msgs);
          if (merged.length > prev.length && nearBottom) {
            shouldScrollRef.current = true;
          }
          return merged;
        });
      } catch { /* silent — next tick will retry */ }
    };
    const id = setInterval(() => void poll(), 3000);
    return () => clearInterval(id);
  }, [conversationId, loading]);

  return (
    <div className="flex flex-col h-full min-h-0 bg-nb-bg">
      {conversation && !loading ? (
        <ConversationHeader conversation={conversation} userRole={userRole} onUpdate={handleConversationUpdated} />
      ) : (
        <HeaderSkeleton />
      )}

      {hasFailedOutbound && (
        <div className="flex items-center gap-2 px-4 py-2.5 bg-nb-danger/5 border-b border-nb-danger/20 flex-shrink-0">
          <AlertTriangle className="w-3.5 h-3.5 text-nb-danger flex-shrink-0" />
          <p className="text-xs text-nb-danger">
            Algumas mensagens não foram entregues pelo WhatsApp. Verifique a configuração do canal ou tente reenviar.
          </p>
        </div>
      )}

      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto min-h-0">
        {loading ? (
          <ThreadSkeleton />
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-8">
            <p className="text-xs text-nb-danger">{error}</p>
            <button
              type="button"
              onClick={() => void load(conversationId)}
              className="px-3 py-1.5 rounded-xl text-xs font-medium bg-nb-elevated text-nb-secondary hover:bg-nb-soft transition-colors"
            >
              Tentar novamente
            </button>
          </div>
        ) : messages.length === 0 ? (
          <EmptyMessages />
        ) : (
          <div className="flex flex-col gap-4 px-5 py-5">
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                msg={msg}
                contactName={conversation?.contact_name ?? null}
                onMessageUpdated={handleMessageUpdated}
              />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {!loading && !error && conversation && (
        <ConversationComposer
          conversationId={conversationId}
          conversationStatus={conversation.status}
          aiEnabled={conversation.ai_enabled}
          userRole={userRole}
          onSent={() => void handleSent()}
          onTakeOver={handleTakeOver}
        />
      )}
    </div>
  );
}
