"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { api } from "@/lib/api";
import type { Agent, ApiError, Conversation } from "@/lib/api";

function friendlyError(e: unknown): string {
  const err = e as ApiError;
  if (err?.status === 403) return "Você não tem permissão para criar conversas.";
  if (err?.status === 422) return "Verifique os dados da conversa.";
  return "Não foi possível criar a conversa.";
}

const inputCls = "w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 disabled:opacity-50 transition-colors";

export function NewConversationModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (conversation: Conversation) => void;
}) {
  const [contactName, setContactName] = useState("");
  const [agentId, setAgentId] = useState<string>("");
  const [aiEnabled, setAiEnabled] = useState(true);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loadingAgents, setLoadingAgents] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    (async () => {
      try {
        const list = await api.agents.list("active");
        setAgents(list);
      } catch { /* non-blocking */ } finally {
        setLoadingAgents(false);
      }
    })();
    setTimeout(() => inputRef.current?.focus(), 50);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setNameError(null);
    setError(null);
    const trimmedName = contactName.trim();
    if (!trimmedName) { setNameError("O nome do contato é obrigatório."); inputRef.current?.focus(); return; }
    setCreating(true);
    try {
      const conv = await api.conversations.create({
        contact_name: trimmedName,
        agent_id: agentId || undefined,
        channel_type: "internal",
        ai_enabled: aiEnabled,
      });
      onCreated(conv);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setCreating(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-md bg-nb-surface border border-nb-border rounded-[18px] shadow-2xl flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-nb-border">
          <h2 className="text-sm font-semibold text-nb-text">Nova conversa</h2>
          <button type="button" onClick={onClose} disabled={creating} className="text-nb-muted hover:text-nb-secondary transition-colors disabled:opacity-40" aria-label="Fechar">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="flex flex-col gap-5 px-5 py-5">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-nb-secondary" htmlFor="contact-name">
              Nome do contato <span className="text-nb-danger">*</span>
            </label>
            <input
              ref={inputRef}
              id="contact-name"
              type="text"
              value={contactName}
              onChange={(e) => { setContactName(e.target.value); setNameError(null); }}
              placeholder="Ex: João Silva"
              disabled={creating}
              className={inputCls}
            />
            {nameError && <p className="text-xs text-nb-danger">{nameError}</p>}
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-nb-secondary" htmlFor="agent-select">
              Agente responsável
            </label>
            <select
              id="agent-select"
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
              disabled={creating || loadingAgents}
              className={inputCls + " cursor-pointer"}
            >
              <option value="">{loadingAgents ? "Carregando agentes…" : "Sem agente"}</option>
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>{agent.name}</option>
              ))}
            </select>
          </div>

          <label className="flex items-center justify-between cursor-pointer select-none">
            <span className="text-xs font-medium text-nb-secondary">IA ativa nesta conversa</span>
            <button
              type="button"
              role="switch"
              aria-checked={aiEnabled}
              onClick={() => setAiEnabled((v) => !v)}
              disabled={creating}
              className={`relative w-9 h-5 rounded-full transition-colors duration-200 flex-shrink-0 focus:outline-none disabled:opacity-50 ${aiEnabled ? "bg-nb-primary" : "bg-nb-border"}`}
            >
              <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${aiEnabled ? "translate-x-4" : "translate-x-0"}`} />
            </button>
          </label>

          <p className="text-xs text-nb-muted/50">
            Canal: <span className="text-nb-muted">Internal</span>
          </p>

          {error && <p className="text-xs text-nb-danger">{error}</p>}

          <div className="flex items-center justify-end gap-3 pt-1">
            <button type="button" onClick={onClose} disabled={creating} className="px-4 py-2 rounded-xl text-xs font-medium text-nb-muted hover:text-nb-secondary transition-colors disabled:opacity-40">
              Cancelar
            </button>
            <button
              type="submit"
              disabled={creating || !contactName.trim()}
              className="px-4 py-2 rounded-xl text-xs font-medium bg-nb-primary text-white hover:bg-nb-primary-strong transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {creating ? "Criando…" : "Criar conversa"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
