"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  Bot,
  Coins,
  Cpu,
  Database,
  MessageSquare,
  Send,
  Sparkles,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import { api, ApiError } from "@/lib/api";
import type {
  Agent,
  AgentTestResponse,
  AiModel,
  MemberRole,
  PlaygroundMessage,
  PlaygroundSession,
  Usage,
} from "@/lib/api";
import { AgentStatusBadge } from "@/components/agents/AgentStatusBadge";
import { PlaygroundSidebar } from "./PlaygroundSidebar";

// ── Types ─────────────────────────────────────────────────────────────────────

type BlockReason =
  | "archived"
  | "no_system_prompt"
  | "no_model"
  | "model_not_executable"
  | "viewer"
  | null;

// ── Helpers ───────────────────────────────────────────────────────────────────

function getBlockReason(
  agent: Agent,
  activeModel: AiModel | null,
  modelExecutable: boolean,
  role: MemberRole | null,
): BlockReason {
  if (role === "viewer") return "viewer";
  if (agent.status === "archived") return "archived";
  if (!agent.system_prompt?.trim()) return "no_system_prompt";
  if (!activeModel) return "no_model";
  if (!modelExecutable) return "model_not_executable";
  return null;
}

function blockMessage(reason: BlockReason): string {
  switch (reason) {
    case "viewer":
      return "Você não tem permissão para testar este agente.";
    case "archived":
      return "Este agente está arquivado e não pode ser testado.";
    case "no_system_prompt":
      return "Configure um system_prompt em Configurações → Prompt antes de testar.";
    case "no_model":
      return "Configure um modelo em Configurações → Modelo antes de testar.";
    case "model_not_executable":
      return "O modelo selecionado não está disponível para execução nesta fase. Selecione um modelo Anthropic ou Nexbrain compatível.";
    default:
      return "";
  }
}

function formatDuration(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

function testErrorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    switch (e.status) {
      case 400: return e.message;
      case 402: return e.message || "Créditos insuficientes ou plano necessário.";
      case 403: return "Você não tem permissão para testar este agente.";
      case 404: return "Agente não encontrado.";
      case 503: return "Erro temporário ao conectar com o modelo. Tente novamente.";
      default:  return e.message || "Erro desconhecido.";
    }
  }
  return e instanceof Error ? e.message : "Erro desconhecido.";
}

// ── Component ─────────────────────────────────────────────────────────────────

export function AgentChat({
  agent,
  activeModel,
  modelExecutable,
  role,
  getToken,
}: {
  agent: Agent;
  activeModel: AiModel | null;
  modelExecutable: boolean;
  role: MemberRole | null;
  getToken: () => Promise<string | null>;
}) {
  // Sessions state
  const [sessions, setSessions] = useState<PlaygroundSession[]>([]);
  const [activeSession, setActiveSession] = useState<PlaygroundSession | null>(null);
  const [sessionsLoading, setSessionsLoading] = useState(true);

  // Messages state
  const [messages, setMessages] = useState<PlaygroundMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);

  // Last run metadata — only available for the current turn, lost on page reload.
  // TODO (Phase 3.2): enrich PlaygroundMessageOut with run metadata so this persists.
  const [lastRunMeta, setLastRunMeta] = useState<AgentTestResponse | null>(null);

  // Input / send state
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  // Right panel
  const [usage, setUsage] = useState<Usage | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const blockReason = getBlockReason(agent, activeModel, modelExecutable, role);
  const isBlocked = blockReason !== null;

  // ── Load session messages ──────────────────────────────────────────────────

  const loadSession = useCallback(
    async (token: string, session: PlaygroundSession) => {
      setMessagesLoading(true);
      setLastRunMeta(null);
      setChatError(null);
      try {
        const data = await api.agents.playground.getSession(token, agent.id, session.id);
        setActiveSession(session);
        setMessages(data.messages);
      } catch {
        setChatError("Erro ao carregar mensagens da conversa.");
      } finally {
        setMessagesLoading(false);
      }
    },
    [agent.id],
  );

  // ── Initial load ───────────────────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false;

    async function init() {
      const token = await getToken();
      if (!token || cancelled) return;

      setSessionsLoading(true);
      try {
        const [sessionsList, usageData] = await Promise.all([
          api.agents.playground.listSessions(token, agent.id),
          api.plans.usage(token),
        ]);

        if (cancelled) return;
        setSessions(sessionsList);
        setUsage(usageData);

        if (sessionsList.length > 0) {
          await loadSession(token, sessionsList[0]);
        } else {
          // Auto-create a first session
          const newSession = await api.agents.playground.createSession(token, agent.id);
          if (cancelled) return;
          setSessions([newSession]);
          setActiveSession(newSession);
          setMessages([]);
        }
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 403) {
          // Viewer or insufficient permission — skip sessions, show block banner only
        } else {
          setChatError("Erro ao carregar conversas do playground.");
        }
      } finally {
        if (!cancelled) setSessionsLoading(false);
      }
    }

    init();
    return () => { cancelled = true; };
  }, [agent.id, getToken, loadSession]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  // ── New session ────────────────────────────────────────────────────────────

  async function handleNewSession() {
    const token = await getToken();
    if (!token) return;
    setChatError(null);
    try {
      const newSession = await api.agents.playground.createSession(token, agent.id);
      setSessions((prev) => [newSession, ...prev]);
      setActiveSession(newSession);
      setMessages([]);
      setLastRunMeta(null);
    } catch {
      setChatError("Erro ao criar nova conversa.");
    }
  }

  // ── Select session ─────────────────────────────────────────────────────────

  async function handleSelectSession(session: PlaygroundSession) {
    if (session.id === activeSession?.id) return;
    const token = await getToken();
    if (!token) return;
    await loadSession(token, session);
  }

  // ── Delete session ─────────────────────────────────────────────────────────

  async function handleDeleteSession(session: PlaygroundSession) {
    const token = await getToken();
    if (!token) return;

    try {
      await api.agents.playground.deleteSession(token, agent.id, session.id);
      const remaining = sessions.filter((s) => s.id !== session.id);
      setSessions(remaining);

      if (activeSession?.id === session.id) {
        setLastRunMeta(null);
        if (remaining.length > 0) {
          await loadSession(token, remaining[0]);
        } else {
          const newSession = await api.agents.playground.createSession(token, agent.id);
          setSessions([newSession]);
          setActiveSession(newSession);
          setMessages([]);
        }
      }
    } catch {
      setChatError("Erro ao excluir conversa.");
    }
  }

  // ── Send message ───────────────────────────────────────────────────────────

  async function handleSend() {
    const text = input.trim();
    if (!text || sending || isBlocked || !activeSession) return;

    setChatError(null);
    setInput("");
    setSending(true);

    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");

      const res = await api.agents.test(token, agent.id, text, activeSession.id);

      // Reload session messages and refresh the sessions list (title + updated_at)
      const [updatedSession, updatedSessions, usageData] = await Promise.all([
        api.agents.playground.getSession(token, agent.id, res.session_id),
        api.agents.playground.listSessions(token, agent.id),
        api.plans.usage(token),
      ]);

      setMessages(updatedSession.messages);
      setLastRunMeta(res);
      setSessions(updatedSessions);
      setUsage(usageData);
      // Keep activeSession in sync with refreshed data
      const refreshed = updatedSessions.find((s) => s.id === res.session_id);
      if (refreshed) setActiveSession(refreshed);
    } catch (e) {
      setChatError(testErrorMessage(e));
      // Reload messages to show what the backend persisted (user msg on provider error)
      try {
        const token = await getToken();
        if (token && activeSession) {
          const data = await api.agents.playground.getSession(
            token,
            agent.id,
            activeSession.id,
          );
          setMessages(data.messages);
        }
      } catch {
        // Silently ignore — the error banner already shows the root cause
      }
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const creditsUsed   = usage?.ai_credits_used ?? null;
  const creditsPerMsg = activeModel?.credits_per_message ?? null;

  // The last assistant message gets run metadata from the current turn (if any)
  const lastAssistantIdx = messages.reduce(
    (last, msg, i) => (msg.role === "assistant" ? i : last),
    -1,
  );

  return (
    <div className="flex gap-3 h-[calc(100vh-280px)] min-h-[520px]">

      {/* ── Sessions sidebar ── */}
      {!isBlocked && (
        <PlaygroundSidebar
          sessions={sessions}
          activeSessionId={activeSession?.id ?? null}
          loading={sessionsLoading}
          onSelect={handleSelectSession}
          onNew={handleNewSession}
          onDelete={handleDeleteSession}
        />
      )}

      {/* ── Chat area ── */}
      <div className="flex-1 flex flex-col bg-white rounded-xl border border-gray-200 overflow-hidden min-w-0">

        {/* Block banner */}
        {isBlocked && (
          <div className="flex items-start gap-3 px-5 py-3 bg-amber-50 border-b border-amber-100">
            <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-amber-700">{blockMessage(blockReason)}</p>
          </div>
        )}

        {/* Messages scroll area */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">

          {/* Empty / loading state */}
          {messagesLoading ? (
            <div className="h-full flex items-center justify-center">
              <div className="flex gap-1">
                <span className="w-2 h-2 rounded-full bg-indigo-300 animate-bounce [animation-delay:0ms]" />
                <span className="w-2 h-2 rounded-full bg-indigo-300 animate-bounce [animation-delay:150ms]" />
                <span className="w-2 h-2 rounded-full bg-indigo-300 animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          ) : messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center py-12">
              <div className="w-14 h-14 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-4">
                <Sparkles className="w-7 h-7 text-indigo-400" />
              </div>
              <h3 className="text-sm font-semibold text-gray-700 mb-1">Agent Playground</h3>
              <p className="text-xs text-gray-400 max-w-xs leading-relaxed">
                {isBlocked
                  ? blockMessage(blockReason)
                  : "Envie uma mensagem para testar seu agente em tempo real."}
              </p>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div
                key={msg.id}
                className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "assistant" && (
                  <div className="w-7 h-7 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Bot className="w-4 h-4 text-indigo-500" />
                  </div>
                )}

                <div
                  className={`flex flex-col gap-1 max-w-[72%] ${
                    msg.role === "user" ? "items-end" : "items-start"
                  }`}
                >
                  <div
                    className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                      msg.role === "user"
                        ? "bg-indigo-600 text-white rounded-br-sm whitespace-pre-wrap"
                        : "bg-gray-100 text-gray-800 rounded-bl-sm"
                    }`}
                  >
                    {msg.role === "user" ? (
                      msg.content
                    ) : (
                      <ReactMarkdown
                        components={{
                          p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                          em: ({ children }) => <em className="italic">{children}</em>,
                          ul: ({ children }) => <ul className="list-disc list-inside mb-1 space-y-0.5">{children}</ul>,
                          ol: ({ children }) => <ol className="list-decimal list-inside mb-1 space-y-0.5">{children}</ol>,
                          li: ({ children }) => <li>{children}</li>,
                          code: ({ children }) => <code className="bg-gray-200 rounded px-1 text-xs font-mono">{children}</code>,
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    )}
                  </div>

                  {/* Run metadata — only for the last assistant message in the current turn */}
                  {msg.role === "assistant" && i === lastAssistantIdx && lastRunMeta && (
                    <div className="flex flex-col gap-0.5 px-1">
                      <p className="text-[11px] text-gray-400">
                        {lastRunMeta.credits_used} crédito{lastRunMeta.credits_used !== 1 ? "s" : ""}
                        {" · "}
                        {formatDuration(lastRunMeta.duration_ms)}
                        {" · "}
                        {lastRunMeta.model.display_name}
                      </p>
                      {lastRunMeta.rag_used && (
                        <span className="inline-flex items-center gap-1 text-[11px] text-emerald-600">
                          <Database className="w-3 h-3" />
                          Conhecimento usado
                          {" · "}
                          {lastRunMeta.retrieved_chunks_count === 1
                            ? "1 trecho"
                            : `${lastRunMeta.retrieved_chunks_count} trechos`}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Timestamp for history messages */}
                  {msg.role === "assistant" && !(i === lastAssistantIdx && lastRunMeta) && (
                    <p className="text-[11px] text-gray-400 px-1">
                      {new Date(msg.created_at).toLocaleTimeString("pt-BR", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  )}
                </div>
              </div>
            ))
          )}

          {/* Typing indicator */}
          {sending && (
            <div className="flex gap-3 justify-start">
              <div className="w-7 h-7 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Bot className="w-4 h-4 text-indigo-500" />
              </div>
              <div className="px-4 py-3 rounded-2xl rounded-bl-sm bg-gray-100">
                <div className="flex gap-1 items-center h-4">
                  <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Error banner */}
        {chatError && (
          <div className="flex items-start gap-2 px-5 py-3 bg-red-50 border-t border-red-100">
            <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-red-600">{chatError}</p>
          </div>
        )}

        {/* Input bar */}
        <div className="border-t border-gray-100 p-4 bg-white">
          <div className="flex items-end gap-2">
            <textarea
              rows={1}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
              }}
              onKeyDown={handleKeyDown}
              disabled={isBlocked || sending}
              placeholder={
                isBlocked
                  ? "Playground indisponível"
                  : "Envie uma mensagem… (Enter para enviar, Shift+Enter para nova linha)"
              }
              className="flex-1 resize-none px-4 py-2.5 rounded-xl border border-gray-200 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-300 disabled:bg-gray-50 disabled:text-gray-400 disabled:cursor-not-allowed leading-relaxed transition-all"
              style={{ minHeight: "42px", maxHeight: "120px" }}
            />
            <button
              type="button"
              onClick={handleSend}
              disabled={isBlocked || sending || !input.trim()}
              className="p-2.5 rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors flex-shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
          <p className="mt-1.5 text-[11px] text-center text-gray-400">
            Histórico persistido automaticamente.
          </p>
        </div>
      </div>

      {/* ── Right info panel ── */}
      <div className="w-60 flex-shrink-0 space-y-3 overflow-y-auto">

        {/* Agent info */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
          <h4 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Agente</h4>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4 text-indigo-500" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-gray-800 truncate">{agent.name}</p>
              <AgentStatusBadge status={agent.status} />
            </div>
          </div>
        </div>

        {/* Model info */}
        {activeModel ? (
          <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-2.5">
            <h4 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Modelo</h4>
            <div className="flex items-center gap-2">
              <Cpu className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
              <span className="text-sm text-gray-700 truncate">{activeModel.display_name}</span>
            </div>
            {creditsPerMsg !== null && creditsPerMsg > 0 && (
              <div className="flex items-center gap-2">
                <Coins className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
                <span className="text-sm text-amber-600">
                  {creditsPerMsg} crédito{creditsPerMsg !== 1 ? "s" : ""}/msg
                </span>
              </div>
            )}
            {!modelExecutable && (
              <p className="text-[11px] text-red-500 leading-snug">
                Modelo não executável nesta fase
              </p>
            )}
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs text-gray-400">Nenhum modelo configurado</p>
          </div>
        )}

        {/* Credits */}
        {usage && (
          <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-2.5">
            <h4 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Créditos</h4>
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Usados</span>
                <span className="font-medium text-gray-700">
                  {creditsUsed?.toLocaleString("pt-BR")}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Tools notice */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-2">
          <h4 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Ferramentas</h4>
          <div className="flex items-start gap-2">
            <Database className="w-3.5 h-3.5 text-gray-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-gray-500">Bases de conhecimento conectadas ao agente são usadas automaticamente.</p>
          </div>
          <div className="flex items-start gap-2">
            <MessageSquare className="w-3.5 h-3.5 text-gray-300 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-gray-400">Nenhuma ferramenta configurada.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
