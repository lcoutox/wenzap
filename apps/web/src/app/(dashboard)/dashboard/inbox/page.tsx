"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
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
      <div className="w-12 h-12 rounded-full bg-nb-elevated border border-nb-border flex items-center justify-center mb-4">
        <svg
          className="w-6 h-6 text-nb-muted"
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
      <h2 className="text-sm font-medium text-nb-secondary">Selecione uma conversa</h2>
      <p className="text-xs text-nb-muted mt-1 max-w-xs">
        As conversas dos canais conectados aparecerão aqui.
      </p>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function InboxContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedId = searchParams.get("conv");

  const [userRole, setUserRole] = useState<MemberRole | null>(null);
  const [listRefreshKey, setListRefreshKey] = useState(0);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    api.me().then((me) => setUserRole(me.role)).catch(() => {});
  }, []);

  const selectConversation = useCallback(
    (id: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("conv", id);
      router.push(`/dashboard/inbox?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  const handleListRefresh = useCallback(() => {
    setListRefreshKey((k) => k + 1);
  }, []);

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

      <main className="flex-1 bg-nb-bg min-w-0 overflow-hidden">
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

export default function InboxPage() {
  return (
    <Suspense>
      <InboxContent />
    </Suspense>
  );
}
