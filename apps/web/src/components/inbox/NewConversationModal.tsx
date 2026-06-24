"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api";
import type { Agent, ApiError, Conversation } from "@/lib/api";

// ── Error mapping ─────────────────────────────────────────────────────────────

function friendlyError(e: unknown): string {
  const err = e as ApiError;
  if (err?.status === 403) return "Você não tem permissão para criar conversas.";
  if (err?.status === 422) return "Verifique os dados da conversa.";
  return "Não foi possível criar a conversa.";
}

// ── Component ─────────────────────────────────────────────────────────────────

export function NewConversationModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (conversation: Conversation) => void;
}) {
  const { getToken } = useAuth();
  const [contactName, setContactName] = useState("");
  const [agentId, setAgentId] = useState<string>("");
  const [aiEnabled, setAiEnabled] = useState(true);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loadingAgents, setLoadingAgents] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load active agents for the select
  useEffect(() => {
    (async () => {
      try {
        const token = await getToken();
        if (!token) return;
        const list = await api.agents.list(token, "active");
        setAgents(list);
      } catch {
        // Non-blocking — agents select will just be empty
      } finally {
        setLoadingAgents(false);
      }
    })();
    // Focus the name field on open
    setTimeout(() => inputRef.current?.focus(), 50);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Close on Escape
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
    if (!trimmedName) {
      setNameError("O nome do contato é obrigatório.");
      inputRef.current?.focus();
      return;
    }

    setCreating(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      const conv = await api.conversations.create(token, {
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
    // Backdrop
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Modal panel */}
      <div className="w-full max-w-md bg-gray-900 border border-gray-800 rounded-xl shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <h2 className="text-sm font-semibold text-white">Nova conversa</h2>
          <button
            type="button"
            onClick={onClose}
            disabled={creating}
            className="text-gray-500 hover:text-gray-300 transition-colors disabled:opacity-40"
            aria-label="Fechar"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={(e) => void handleSubmit(e)} className="flex flex-col gap-5 px-5 py-5">
          {/* Contact name */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-gray-300" htmlFor="contact-name">
              Nome do contato <span className="text-red-400">*</span>
            </label>
            <input
              ref={inputRef}
              id="contact-name"
              type="text"
              value={contactName}
              onChange={(e) => { setContactName(e.target.value); setNameError(null); }}
              placeholder="Ex: João Silva"
              disabled={creating}
              className="
                bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100
                placeholder-gray-600 focus:outline-none focus:border-indigo-500
                focus:ring-1 focus:ring-indigo-500/40 disabled:opacity-50 transition-colors
              "
            />
            {nameError && <p className="text-xs text-red-400">{nameError}</p>}
          </div>

          {/* Agent select */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-gray-300" htmlFor="agent-select">
              Agente responsável
            </label>
            <select
              id="agent-select"
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
              disabled={creating || loadingAgents}
              className="
                bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200
                focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/40
                disabled:opacity-50 cursor-pointer transition-colors
              "
            >
              <option value="">
                {loadingAgents ? "Carregando agentes…" : "Sem agente"}
              </option>
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
          </div>

          {/* AI toggle */}
          <label className="flex items-center justify-between cursor-pointer select-none">
            <span className="text-xs font-medium text-gray-300">IA ativa nesta conversa</span>
            <button
              type="button"
              role="switch"
              aria-checked={aiEnabled}
              onClick={() => setAiEnabled((v) => !v)}
              disabled={creating}
              className={`
                relative w-9 h-5 rounded-full transition-colors duration-200 flex-shrink-0
                focus:outline-none disabled:opacity-50
                ${aiEnabled ? "bg-indigo-600" : "bg-gray-700"}
              `}
            >
              <span
                className={`
                  absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200
                  ${aiEnabled ? "translate-x-4" : "translate-x-0"}
                `}
              />
            </button>
          </label>

          {/* Channel info */}
          <p className="text-xs text-gray-600">
            Canal: <span className="text-gray-500">Internal</span>
          </p>

          {/* Submit error */}
          {error && <p className="text-xs text-red-400">{error}</p>}

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              disabled={creating}
              className="px-4 py-2 rounded-lg text-xs font-medium text-gray-400 hover:text-gray-200 transition-colors disabled:opacity-40"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={creating || !contactName.trim()}
              className="
                px-4 py-2 rounded-lg text-xs font-medium bg-indigo-600 text-white
                hover:bg-indigo-500 transition-colors
                disabled:opacity-40 disabled:cursor-not-allowed
              "
            >
              {creating ? "Criando…" : "Criar conversa"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
