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
  PackageSearch,
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
  if (!activeModel) return "no_model";
  if (!modelExecutable) return "model_not_executable";
  return null;
}

function blockMessage(reason: BlockReason): string {
  switch (reason) {
    case "viewer":              return "Você não tem permissão para testar este agente.";
    case "archived":            return "Este agente está arquivado e não pode ser testado.";
    case "no_model":            return "Configure um modelo em Configurações → Modelo antes de testar.";
    case "model_not_executable":return "O modelo selecionado não está disponível para execução. Selecione um modelo Anthropic Claude ou OpenAI GPT compatível.";
    default:                    return "";
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

// ── Catalog info (Playground) ─────────────────────────────────────────────────

function PlaygroundCatalogInfo({ meta }: { meta: AgentTestResponse }) {
  const [open, setOpen] = useState(false);
  const count = meta.catalog_items_count;
  const method = meta.catalog_retrieval_method;
  const items = meta.catalog_items_used ?? [];

  const methodLabel = (m: string | null) => {
    if (m === "hybrid") return "híbrido";
    if (m === "lexical_fallback") return "lexical";
    if (m === "semantic") return "semântico";
    if (m === "lexical") return "lexical";
    return m ?? "—";
  };

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 text-[11px] text-nb-muted hover:text-nb-secondary transition-colors"
      >
        <PackageSearch className="w-3 h-3" />
        Catálogo consultado
        {count > 0 && ` · ${count} item${count !== 1 ? "s" : ""}`}
        {count === 0 && " · sem itens"}
        {method && ` · ${methodLabel(method)}`}
      </button>

      {open && (
        <div className="mt-1.5 rounded-xl border border-nb-border bg-nb-bg px-3 py-2.5 space-y-2 text-[11px] text-nb-secondary">
          {count === 0 ? (
            <p className="text-nb-muted">Nenhum item relevante encontrado.</p>
          ) : (
            <ol className="space-y-1.5">
              {items.map((item, idx) => (
                <li key={item.id ?? idx}>
                  <p className="font-medium text-nb-text">{idx + 1}. {item.name ?? "Item sem nome"}</p>
                  <div className="flex flex-wrap gap-x-3 text-nb-muted">
                    {item.score != null && (
                      <span>Score: <span className="text-nb-secondary">{item.score.toFixed(2)}</span></span>
                    )}
                    {item.semantic_score != null && (
                      <span>Semântico: <span className="text-nb-secondary">{item.semantic_score.toFixed(2)}</span></span>
                    )}
                    {item.lexical_score != null && (
                      <span>Lexical: <span className="text-nb-secondary">{item.lexical_score.toFixed(2)}</span></span>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export function AgentChat({
  agent,
  activeModel,
  modelExecutable,
  role,
}: {
  agent: Agent;
  activeModel: AiModel | null;
  modelExecutable: boolean;
  role: MemberRole | null;
}) {
  const [sessions, setSessions] = useState<PlaygroundSession[]>([]);
  const [activeSession, setActiveSession] = useState<PlaygroundSession | null>(null);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [messages, setMessages] = useState<PlaygroundMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [lastRunMeta, setLastRunMeta] = useState<AgentTestResponse | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const blockReason = getBlockReason(agent, activeModel, modelExecutable, role);
  const isBlocked = blockReason !== null;

  const loadSession = useCallback(
    async (session: PlaygroundSession) => {
      setMessagesLoading(true);
      setLastRunMeta(null);
      setChatError(null);
      try {
        const data = await api.agents.playground.getSession(agent.id, session.id);
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

  useEffect(() => {
    let cancelled = false;
    async function init() {
      if (cancelled) return;
      setSessionsLoading(true);
      try {
        const [sessionsList, usageData] = await Promise.all([
          api.agents.playground.listSessions(agent.id),
          api.plans.usage(),
        ]);
        if (cancelled) return;
        setSessions(sessionsList);
        setUsage(usageData);
        if (sessionsList.length > 0) {
          await loadSession(sessionsList[0]);
        } else {
          const newSession = await api.agents.playground.createSession(agent.id);
          if (cancelled) return;
          setSessions([newSession]);
          setActiveSession(newSession);
          setMessages([]);
        }
      } catch (e) {
        if (cancelled) return;
        if (!(e instanceof ApiError && e.status === 403)) {
          setChatError("Erro ao carregar conversas do playground.");
        }
      } finally {
        if (!cancelled) setSessionsLoading(false);
      }
    }
    init();
    return () => { cancelled = true; };
  }, [agent.id, loadSession]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function handleNewSession() {
    setChatError(null);
    try {
      const newSession = await api.agents.playground.createSession(agent.id);
      setSessions((prev) => [newSession, ...prev]);
      setActiveSession(newSession);
      setMessages([]);
      setLastRunMeta(null);
    } catch {
      setChatError("Erro ao criar nova conversa.");
    }
  }

  async function handleSelectSession(session: PlaygroundSession) {
    if (session.id === activeSession?.id) return;
    await loadSession(session);
  }

  async function handleDeleteSession(session: PlaygroundSession) {
    try {
      await api.agents.playground.deleteSession(agent.id, session.id);
      const remaining = sessions.filter((s) => s.id !== session.id);
      setSessions(remaining);
      if (activeSession?.id === session.id) {
        setLastRunMeta(null);
        if (remaining.length > 0) {
          await loadSession(remaining[0]);
        } else {
          const newSession = await api.agents.playground.createSession(agent.id);
          setSessions([newSession]);
          setActiveSession(newSession);
          setMessages([]);
        }
      }
    } catch {
      setChatError("Erro ao excluir conversa.");
    }
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || sending || isBlocked || !activeSession) return;
    setChatError(null);
    setInput("");
    setSending(true);
    try {
      const res = await api.agents.test(agent.id, text, activeSession.id);
      const [updatedSession, updatedSessions, usageData] = await Promise.all([
        api.agents.playground.getSession(agent.id, res.session_id),
        api.agents.playground.listSessions(agent.id),
        api.plans.usage(),
      ]);
      setMessages(updatedSession.messages);
      setLastRunMeta(res);
      setSessions(updatedSessions);
      setUsage(usageData);
      const refreshed = updatedSessions.find((s) => s.id === res.session_id);
      if (refreshed) setActiveSession(refreshed);
    } catch (e) {
      setChatError(testErrorMessage(e));
      try {
        if (activeSession) {
          const data = await api.agents.playground.getSession(agent.id, activeSession.id);
          setMessages(data.messages);
        }
      } catch { /* ignore */ }
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
  const lastAssistantIdx = messages.reduce(
    (last, msg, i) => (msg.role === "assistant" ? i : last),
    -1,
  );

  return (
    <div className="flex gap-3 h-[calc(100vh-280px)] min-h-[520px]">

      {/* Sessions sidebar */}
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

      {/* Chat area */}
      <div className="flex-1 flex flex-col bg-nb-panel rounded-2xl border border-nb-border overflow-hidden min-w-0">

        {/* Block banner */}
        {isBlocked && (
          <div className="flex items-start gap-3 px-5 py-3 bg-nb-warning/10 border-b border-nb-warning/20">
            <AlertTriangle className="w-4 h-4 text-nb-warning mt-0.5 flex-shrink-0" />
            <p className="text-sm text-nb-warning">{blockMessage(blockReason)}</p>
          </div>
        )}

        {/* Messages scroll area */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {messagesLoading ? (
            <div className="h-full flex items-center justify-center">
              <div className="flex gap-1">
                <span className="w-2 h-2 rounded-full bg-nb-primary animate-bounce [animation-delay:0ms]" />
                <span className="w-2 h-2 rounded-full bg-nb-primary animate-bounce [animation-delay:150ms]" />
                <span className="w-2 h-2 rounded-full bg-nb-primary animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          ) : messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center py-12">
              <div className="w-14 h-14 rounded-2xl bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center mb-4">
                <Sparkles className="w-7 h-7 text-nb-primary-strong" />
              </div>
              <h3 className="text-sm font-semibold text-nb-secondary mb-1">Agent Playground</h3>
              <p className="text-xs text-nb-muted max-w-xs leading-relaxed">
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
                  <div className="w-7 h-7 rounded-xl bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Bot className="w-4 h-4 text-nb-primary-strong" />
                  </div>
                )}

                <div className={`flex flex-col gap-1 max-w-[72%] ${
                  msg.role === "user" ? "items-end" : "items-start"
                }`}>
                  <div className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-nb-primary text-white rounded-br-sm whitespace-pre-wrap"
                      : "bg-nb-elevated text-nb-text rounded-bl-sm"
                  }`}>
                    {msg.role === "user" ? (
                      msg.content
                    ) : (
                      <ReactMarkdown
                        components={{
                          p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                          strong: ({ children }) => <strong className="font-semibold text-nb-text">{children}</strong>,
                          em: ({ children }) => <em className="italic">{children}</em>,
                          ul: ({ children }) => <ul className="list-disc list-inside mb-1 space-y-0.5">{children}</ul>,
                          ol: ({ children }) => <ol className="list-decimal list-inside mb-1 space-y-0.5">{children}</ol>,
                          li: ({ children }) => <li>{children}</li>,
                          code: ({ children }) => <code className="bg-nb-soft rounded px-1 text-xs font-mono text-nb-info">{children}</code>,
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    )}
                  </div>

                  {msg.role === "assistant" && i === lastAssistantIdx && lastRunMeta && (
                    <div className="flex flex-col gap-0.5 px-1">
                      <p className="text-[11px] text-nb-muted">
                        {lastRunMeta.credits_used} crédito{lastRunMeta.credits_used !== 1 ? "s" : ""}
                        {" · "}
                        {formatDuration(lastRunMeta.duration_ms)}
                        {" · "}
                        {lastRunMeta.model.display_name}
                      </p>
                      {lastRunMeta.rag_used && (
                        <span className="inline-flex items-center gap-1 text-[11px] text-nb-success">
                          <Database className="w-3 h-3" />
                          Conhecimento usado
                          {" · "}
                          {lastRunMeta.retrieved_chunks_count === 1
                            ? "1 trecho"
                            : `${lastRunMeta.retrieved_chunks_count} trechos`}
                        </span>
                      )}
                      {lastRunMeta.catalog_retrieval_attempted && (
                        <PlaygroundCatalogInfo meta={lastRunMeta} />
                      )}
                    </div>
                  )}

                  {msg.role === "assistant" && !(i === lastAssistantIdx && lastRunMeta) && (
                    <p className="text-[11px] text-nb-muted px-1">
                      {new Date(msg.created_at).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
                    </p>
                  )}
                </div>
              </div>
            ))
          )}

          {/* Typing indicator */}
          {sending && (
            <div className="flex gap-3 justify-start">
              <div className="w-7 h-7 rounded-xl bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Bot className="w-4 h-4 text-nb-primary-strong" />
              </div>
              <div className="px-4 py-3 rounded-2xl rounded-bl-sm bg-nb-elevated">
                <div className="flex gap-1 items-center h-4">
                  <span className="w-1.5 h-1.5 rounded-full bg-nb-muted animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-nb-muted animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-nb-muted animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Error banner */}
        {chatError && (
          <div className="flex items-start gap-2 px-5 py-3 bg-nb-danger/10 border-t border-nb-danger/20">
            <AlertCircle className="w-4 h-4 text-nb-danger mt-0.5 flex-shrink-0" />
            <p className="text-sm text-nb-danger">{chatError}</p>
          </div>
        )}

        {/* Input bar */}
        <div className="border-t border-nb-border p-4 bg-nb-surface">
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
              className="flex-1 resize-none px-4 py-2.5 rounded-xl border border-nb-border bg-nb-elevated text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 disabled:opacity-50 disabled:cursor-not-allowed leading-relaxed transition-all"
              style={{ minHeight: "42px", maxHeight: "120px" }}
            />
            <button
              type="button"
              onClick={handleSend}
              disabled={isBlocked || sending || !input.trim()}
              className="p-2.5 rounded-xl bg-nb-primary text-white hover:bg-nb-primary-strong disabled:bg-nb-elevated disabled:text-nb-muted disabled:cursor-not-allowed transition-colors flex-shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
          <p className="mt-1.5 text-[11px] text-center text-nb-muted">
            Histórico persistido automaticamente.
          </p>
        </div>
      </div>

      {/* Right info panel */}
      <div className="w-60 flex-shrink-0 space-y-3 overflow-y-auto">

        <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 space-y-3">
          <h4 className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Agente</h4>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4 text-nb-primary-strong" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-nb-text truncate">{agent.name}</p>
              <AgentStatusBadge status={agent.status} />
            </div>
          </div>
        </div>

        {activeModel ? (
          <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 space-y-2.5">
            <h4 className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Modelo</h4>
            <div className="flex items-center gap-2">
              <Cpu className="w-3.5 h-3.5 text-nb-muted flex-shrink-0" />
              <span className="text-sm text-nb-secondary truncate">{activeModel.display_name}</span>
            </div>
            {creditsPerMsg !== null && creditsPerMsg > 0 && (
              <div className="flex items-center gap-2">
                <Coins className="w-3.5 h-3.5 text-nb-warning flex-shrink-0" />
                <span className="text-sm text-nb-warning">
                  {creditsPerMsg} crédito{creditsPerMsg !== 1 ? "s" : ""}/msg
                </span>
              </div>
            )}
            {!modelExecutable && (
              <p className="text-[11px] text-nb-danger leading-snug">
                Modelo não executável nesta fase
              </p>
            )}
          </div>
        ) : (
          <div className="bg-nb-panel rounded-2xl border border-nb-border p-4">
            <p className="text-xs text-nb-muted">Nenhum modelo configurado</p>
          </div>
        )}

        {usage && (
          <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 space-y-2.5">
            <h4 className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Créditos</h4>
            <div className="flex justify-between text-xs">
              <span className="text-nb-muted">Usados</span>
              <span className="font-medium text-nb-secondary">
                {creditsUsed?.toLocaleString("pt-BR")}
              </span>
            </div>
          </div>
        )}

        <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 space-y-2">
          <h4 className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Ferramentas</h4>
          <div className="flex items-start gap-2">
            <Database className="w-3.5 h-3.5 text-nb-muted flex-shrink-0 mt-0.5" />
            <p className="text-xs text-nb-muted">Bases de conhecimento conectadas são usadas automaticamente.</p>
          </div>
          <div className="flex items-start gap-2">
            <MessageSquare className="w-3.5 h-3.5 text-nb-border-strong flex-shrink-0 mt-0.5" />
            <p className="text-xs text-nb-muted/60">Nenhuma ferramenta configurada.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
