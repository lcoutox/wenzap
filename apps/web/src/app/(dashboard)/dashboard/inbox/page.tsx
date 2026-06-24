"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Conversation, MemberRole } from "@/lib/api";
import { ConversationList } from "@/components/inbox/ConversationList";
import { ConversationThread } from "@/components/inbox/ConversationThread";
import { NewConversationModal } from "@/components/inbox/NewConversationModal";

// ── RBAC ──────────────────────────────────────────────────────────────────────

function canWrite(role: MemberRole | null) {
  return role === "owner" || role === "admin" || role === "member";
}

// ── Empty panel ───────────────────────────────────────────────────────────────

function EmptyPanel() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-8">
      <div className="w-12 h-12 rounded-full bg-gray-800/60 flex items-center justify-center mb-4">
        <svg
          className="w-6 h-6 text-gray-600"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
      </div>
      <h2 className="text-sm font-medium text-gray-400">Selecione uma conversa</h2>
      <p className="text-xs text-gray-600 mt-1 max-w-xs">
        As conversas dos canais conectados aparecerão aqui.
      </p>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function InboxPage() {
  const { getToken } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedId = searchParams.get("conv");

  const [userRole, setUserRole] = useState<MemberRole | null>(null);
  const [listRefreshKey, setListRefreshKey] = useState(0);
  const [showModal, setShowModal] = useState(false);

  // Fetch the current user's role once on mount (used for the Nova conversa button).
  useEffect(() => {
    (async () => {
      try {
        const token = await getToken();
        if (!token) return;
        const me = await api.me(token);
        setUserRole(me.role);
      } catch {
        // Non-critical — button will stay hidden.
      }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectConversation = useCallback(
    (id: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("conv", id);
      router.push(`/dashboard/inbox?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  // Both message sends and conversation updates (status/AI) refresh the list.
  const handleListRefresh = useCallback(() => {
    setListRefreshKey((k) => k + 1);
  }, []);

  // Called after a new conversation is created in the modal.
  const handleConversationCreated = useCallback(
    (conv: Conversation) => {
      setShowModal(false);
      handleListRefresh();
      selectConversation(conv.id);
    },
    [handleListRefresh, selectConversation],
  );

  return (
    // -m-6 cancels DashboardShell's p-6; height fills viewport below header (h-14 = 3.5rem)
    <div className="-m-6 flex overflow-hidden" style={{ height: "calc(100vh - 3.5rem)" }}>
      <ConversationList
        selectedId={selectedId}
        onSelect={selectConversation}
        refreshKey={listRefreshKey}
        canCreate={canWrite(userRole)}
        onNewConversation={() => setShowModal(true)}
      />

      <main className="flex-1 bg-gray-950 min-w-0 overflow-hidden">
        {selectedId ? (
          <ConversationThread
            conversationId={selectedId}
            onMessageSent={handleListRefresh}
            onConversationUpdated={handleListRefresh}
          />
        ) : (
          <EmptyPanel />
        )}
      </main>

      {showModal && (
        <NewConversationModal
          onClose={() => setShowModal(false)}
          onCreated={handleConversationCreated}
        />
      )}
    </div>
  );
}
