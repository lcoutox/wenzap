"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { api } from "@/lib/api";
import type { Contact, Conversation } from "@/lib/api";
import { ConversationItem } from "./ConversationItem";

type Filter = "all" | "open" | "pending" | "resolved" | "archived";

const FILTERS: { value: Filter; label: string; emptyLabel: string }[] = [
  { value: "all",      label: "Todas",     emptyLabel: "Nenhuma conversa encontrada."  },
  { value: "open",     label: "Abertas",   emptyLabel: "Nenhuma conversa aberta."      },
  { value: "pending",  label: "Pendentes", emptyLabel: "Nenhuma conversa pendente."    },
  { value: "resolved", label: "Resolvidas",emptyLabel: "Nenhuma conversa resolvida."   },
  { value: "archived", label: "Arquivadas",emptyLabel: "Nenhuma conversa arquivada."   },
];

function Skeleton() {
  return (
    <div className="space-y-0">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="px-3 py-3 border-b border-nb-border/60 animate-pulse">
          <div className="flex justify-between mb-2">
            <div className="h-3 bg-nb-elevated rounded w-2/3" />
            <div className="h-3 bg-nb-elevated rounded w-8" />
          </div>
          <div className="flex gap-1.5">
            <div className="h-3 bg-nb-elevated rounded w-12" />
            <div className="h-3 bg-nb-elevated rounded w-14" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function ConversationList({
  selectedId,
  onSelect,
  refreshKey = 0,
  canCreate = false,
  onNewConversation,
  filterContact = null,
  onClearContactFilter,
}: {
  selectedId: string | null;
  onSelect: (id: string) => void;
  refreshKey?: number;
  canCreate?: boolean;
  onNewConversation?: () => void;
  filterContact?: Contact | null;
  onClearContactFilter?: () => void;
}) {
  const [activeFilter, setActiveFilter] = useState<Filter>("all");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Keep filter in a ref so the polling closure always reads the latest value.
  const activeFilterRef = useRef<Filter>("all");
  const filterContactRef = useRef<Contact | null>(null);
  filterContactRef.current = filterContact ?? null;

  const load = async (filter: Filter, contactId?: string) => {
    setLoading(true);
    setError(null);
    try {
      const status = filter === "all" ? undefined : filter;
      const data = await api.conversations.list({ status, contact_id: contactId, limit: 50 });
      setConversations(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar conversas.");
    } finally {
      setLoading(false);
    }
  };

  const silentPoll = async () => {
    if (document.hidden) return;
    try {
      const status = activeFilterRef.current === "all" ? undefined : activeFilterRef.current;
      const data = await api.conversations.list({ status, contact_id: filterContactRef.current?.id, limit: 50 });
      setConversations(data);
    } catch { /* silent */ }
  };

  useEffect(() => {
    activeFilterRef.current = activeFilter;
    void load(activeFilter, filterContact?.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFilter, refreshKey, filterContact?.id]);

  // Polling — silent refresh every 5 s.
  useEffect(() => {
    const id = setInterval(() => void silentPoll(), 5000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const emptyLabel = FILTERS.find((f) => f.value === activeFilter)?.emptyLabel ?? "Nenhuma conversa encontrada.";

  return (
    <aside className="w-72 flex-shrink-0 border-r border-nb-border flex flex-col bg-nb-surface min-h-0">
      <div className="flex items-center justify-between px-4 py-3 border-b border-nb-border flex-shrink-0">
        <h1 className="text-sm font-semibold text-nb-text">Inbox</h1>
        {canCreate && (
          <button
            type="button"
            onClick={onNewConversation}
            className="px-2.5 py-1 rounded-lg text-xs font-medium bg-nb-primary-bg text-nb-primary-strong hover:bg-nb-primary/20 transition-colors"
          >
            + Nova conversa
          </button>
        )}
      </div>

      {filterContact && (
        <div className="px-3 py-2 border-b border-nb-border flex-shrink-0 bg-nb-primary-bg/30">
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-nb-muted">Contato:</span>
            <span className="text-xs font-medium text-nb-primary-strong truncate flex-1">
              {filterContact.name || filterContact.email || filterContact.phone}
            </span>
            <button
              type="button"
              onClick={onClearContactFilter}
              className="p-0.5 rounded hover:bg-nb-primary/20 text-nb-primary-strong transition-colors"
              title="Limpar filtro"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}

      <div className="flex gap-0 border-b border-nb-border flex-shrink-0 overflow-x-auto">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => { if (f.value !== activeFilter) setActiveFilter(f.value); }}
            className={`flex-shrink-0 px-3 py-2 text-xs font-medium transition-colors border-b-2 ${
              activeFilter === f.value
                ? "text-nb-primary-strong border-nb-primary"
                : "text-nb-muted border-transparent hover:text-nb-secondary"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        {loading ? (
          <Skeleton />
        ) : error ? (
          <div className="flex flex-col items-center justify-center px-4 py-10 text-center gap-3">
            <p className="text-xs text-nb-danger">{error}</p>
            <button
              type="button"
              onClick={() => void load(activeFilter)}
              className="px-3 py-1.5 rounded-xl text-xs font-medium bg-nb-elevated text-nb-secondary hover:bg-nb-soft transition-colors"
            >
              Tentar novamente
            </button>
          </div>
        ) : conversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
            <p className="text-xs text-nb-muted">{emptyLabel}</p>
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
