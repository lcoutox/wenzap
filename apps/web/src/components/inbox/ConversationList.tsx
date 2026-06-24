"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api";
import type { Conversation } from "@/lib/api";
import { ConversationItem } from "./ConversationItem";

// ── Filter config ─────────────────────────────────────────────────────────────

type Filter = "all" | "open" | "pending" | "resolved" | "archived";

const FILTERS: { value: Filter; label: string; emptyLabel: string }[] = [
  { value: "all",      label: "Todas",     emptyLabel: "Nenhuma conversa encontrada."  },
  { value: "open",     label: "Abertas",   emptyLabel: "Nenhuma conversa aberta."      },
  { value: "pending",  label: "Pendentes", emptyLabel: "Nenhuma conversa pendente."    },
  { value: "resolved", label: "Resolvidas",emptyLabel: "Nenhuma conversa resolvida."   },
  { value: "archived", label: "Arquivadas",emptyLabel: "Nenhuma conversa arquivada."   },
];

// ── Skeleton ──────────────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div className="space-y-0">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="px-3 py-3 border-b border-gray-800/60 animate-pulse">
          <div className="flex justify-between mb-2">
            <div className="h-3 bg-gray-700 rounded w-2/3" />
            <div className="h-3 bg-gray-700 rounded w-8" />
          </div>
          <div className="flex gap-1.5">
            <div className="h-3 bg-gray-700 rounded w-12" />
            <div className="h-3 bg-gray-700 rounded w-14" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export function ConversationList({
  selectedId,
  onSelect,
  refreshKey = 0,
  canCreate = false,
  onNewConversation,
}: {
  selectedId: string | null;
  onSelect: (id: string) => void;
  refreshKey?: number;
  canCreate?: boolean;
  onNewConversation?: () => void;
}) {
  const { getToken } = useAuth();
  const [activeFilter, setActiveFilter] = useState<Filter>("all");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async (filter: Filter) => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada. Recarregue a página.");
      const status = filter === "all" ? undefined : filter;
      const data = await api.conversations.list(token, { status, limit: 50 });
      setConversations(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar conversas.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(activeFilter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFilter, refreshKey]);

  const handleFilter = (f: Filter) => {
    if (f !== activeFilter) setActiveFilter(f);
  };

  const emptyLabel =
    FILTERS.find((f) => f.value === activeFilter)?.emptyLabel ??
    "Nenhuma conversa encontrada.";

  return (
    <aside className="w-72 flex-shrink-0 border-r border-gray-800 flex flex-col bg-gray-900 min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 flex-shrink-0">
        <h1 className="text-sm font-semibold text-white">Inbox</h1>
        {canCreate ? (
          <button
            type="button"
            onClick={onNewConversation}
            className="px-2.5 py-1 rounded text-xs font-medium bg-indigo-600/20 text-indigo-400 hover:bg-indigo-600/30 transition-colors"
          >
            + Nova conversa
          </button>
        ) : null}
      </div>

      {/* Status tabs */}
      <div className="flex gap-0 border-b border-gray-800 flex-shrink-0 overflow-x-auto">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => handleFilter(f.value)}
            className={`
              flex-shrink-0 px-3 py-2 text-xs font-medium transition-colors border-b-2
              ${activeFilter === f.value
                ? "text-indigo-400 border-indigo-500"
                : "text-gray-500 border-transparent hover:text-gray-300"}
            `}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {loading ? (
          <Skeleton />
        ) : error ? (
          <div className="flex flex-col items-center justify-center px-4 py-10 text-center gap-3">
            <p className="text-xs text-red-400">{error}</p>
            <button
              type="button"
              onClick={() => void load(activeFilter)}
              className="px-3 py-1.5 rounded text-xs font-medium bg-gray-800 text-gray-300 hover:bg-gray-700 transition-colors"
            >
              Tentar novamente
            </button>
          </div>
        ) : conversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
            <p className="text-xs text-gray-500">{emptyLabel}</p>
          </div>
        ) : (
          conversations.map((conv) => (
            <ConversationItem
              key={conv.id}
              conversation={conv}
              isSelected={conv.id === selectedId}
              onClick={() => onSelect(conv.id)}
            />
          ))
        )}
      </div>
    </aside>
  );
}
