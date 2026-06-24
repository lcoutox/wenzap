"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api";
import type { Conversation, ConversationMessage, MemberRole } from "@/lib/api";
import { MessageBubble } from "./MessageBubble";
import { ConversationComposer } from "./ConversationComposer";
import { ConversationHeader } from "./ConversationHeader";

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
  const { getToken } = useAuth();
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [userRole, setUserRole] = useState<MemberRole | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "instant" });
  }, []);

  const load = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada. Recarregue a página.");
      const [conv, msgs, me] = await Promise.all([
        api.conversations.get(token, id),
        api.conversations.messages.list(token, id, { limit: 200 }),
        api.me(token),
      ]);
      setConversation(conv);
      setMessages(msgs);
      setUserRole(me.role);
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

  const reloadMessages = useCallback(async () => {
    const token = await getToken();
    if (!token || !conversation) return;
    try {
      const msgs = await api.conversations.messages.list(token, conversationId, { limit: 200 });
      setMessages(msgs);
    } catch { /* ignore */ }
  }, [getToken, conversationId, conversation]);

  const handleSent = useCallback(async () => {
    await reloadMessages();
    onMessageSent();
    scrollToBottom();
  }, [reloadMessages, onMessageSent, scrollToBottom]);

  useEffect(() => {
    void load(conversationId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  useEffect(() => {
    if (!loading && messages.length > 0) scrollToBottom();
  }, [loading, messages, scrollToBottom]);

  return (
    <div className="flex flex-col h-full min-h-0 bg-nb-bg">
      {conversation && !loading ? (
        <ConversationHeader conversation={conversation} userRole={userRole} onUpdate={handleConversationUpdated} />
      ) : (
        <HeaderSkeleton />
      )}

      <div className="flex-1 overflow-y-auto min-h-0">
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
              <MessageBubble key={msg.id} msg={msg} contactName={conversation?.contact_name ?? null} />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {!loading && !error && conversation && (
        <ConversationComposer
          conversationId={conversationId}
          conversationStatus={conversation.status}
          userRole={userRole}
          onSent={() => void handleSent()}
        />
      )}
    </div>
  );
}
