"use client";

import { MessageSquare, Plus, Trash2 } from "lucide-react";
import type { PlaygroundSession } from "@/lib/api";

function formatRelativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "Agora mesmo";
  if (minutes < 60) return `${minutes}m atrás`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h atrás`;
  return `${Math.floor(hours / 24)}d atrás`;
}

export function PlaygroundSidebar({
  sessions,
  activeSessionId,
  loading,
  onSelect,
  onNew,
  onDelete,
}: {
  sessions: PlaygroundSession[];
  activeSessionId: string | null;
  loading: boolean;
  onSelect: (session: PlaygroundSession) => void;
  onNew: () => void;
  onDelete: (session: PlaygroundSession) => void;
}) {
  return (
    <div className="w-52 flex-shrink-0 flex flex-col bg-nb-surface rounded-2xl border border-nb-border overflow-hidden">
      {/* Header */}
      <div className="p-3 border-b border-nb-border">
        <button
          type="button"
          onClick={onNew}
          disabled={loading}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium text-nb-primary bg-nb-primary-bg hover:bg-nb-primary/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <Plus className="w-3.5 h-3.5 flex-shrink-0" />
          Nova conversa
        </button>
      </div>

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto">
        {loading && sessions.length === 0 ? (
          <div className="p-3 space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 rounded-xl bg-nb-elevated animate-pulse" />
            ))}
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-24 text-center px-3">
            <MessageSquare className="w-5 h-5 text-nb-border-strong mb-1.5" />
            <p className="text-xs text-nb-muted">Nenhuma conversa ainda</p>
          </div>
        ) : (
          <ul className="p-2 space-y-0.5">
            {sessions.map((session) => {
              const isActive = session.id === activeSessionId;
              return (
                <li key={session.id}>
                  <div
                    role="button"
                    tabIndex={0}
                    onClick={() => onSelect(session)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onSelect(session); }}
                    className={`w-full text-left px-3 py-2 rounded-xl group flex items-start gap-2 transition-colors cursor-pointer ${
                      isActive
                        ? "bg-nb-primary-bg text-nb-primary-strong"
                        : "text-nb-secondary hover:bg-nb-elevated"
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <p className={`text-xs font-medium truncate leading-tight ${
                        isActive ? "text-nb-primary-strong" : "text-nb-secondary"
                      }`}>
                        {session.title}
                      </p>
                      <p className="text-[10px] text-nb-muted mt-0.5">
                        {formatRelativeTime(session.updated_at)}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); onDelete(session); }}
                      className="flex-shrink-0 p-0.5 rounded opacity-0 group-hover:opacity-100 hover:text-nb-danger transition-all mt-0.5"
                      aria-label="Excluir conversa"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
