"use client";

import { useEffect, useRef, useState } from "react";
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
import { api, ApiError } from "@/lib/api";
import type { Agent, AgentTestResponse, AiModel, MemberRole, Usage } from "@/lib/api";
import { AgentStatusBadge } from "@/components/agents/AgentStatusBadge";

// ── Types ─────────────────────────────────────────────────────────────────────

type ChatMessage =
  | { role: "user"; content: string }
  | { role: "agent"; content: string; meta: AgentTestResponse };

type BlockReason =
  | "archived"
  | "no_system_prompt"
  | "no_model"
  | "model_not_executable"
  | "viewer"
  | null;

// ── Helpers ───────────────────────────────────────────────────────────────────

// Phase 3: only these model_name values are executable via Anthropic
const EXECUTABLE_MODELS = new Set([
  "claude-haiku-4-5",
  "claude-sonnet-4-6",
  "claude-opus-4-8",
]);

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

function errorMessage(e: unknown): string {
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
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const blockReason = getBlockReason(agent, activeModel, modelExecutable, role);
  const isBlocked = blockReason !== null;

  // Load usage for credit panel
  useEffect(() => {
    getToken().then((token) => {
      if (!token) return;
      api.plans.usage(token).then(setUsage).catch(() => null);
    });
  }, [getToken]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    const text = input.trim();
    if (!text || sending || isBlocked) return;

    setChatError(null);
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setSending(true);

    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      const res = await api.agents.test(token, agent.id, text);
      setMessages((prev) => [...prev, { role: "agent", content: res.reply, meta: res }]);
      // Refresh usage after a successful call
      api.plans.usage(token).then(setUsage).catch(() => null);
    } catch (e) {
      setChatError(errorMessage(e));
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

  const creditsUsed    = usage?.ai_credits_used ?? null;
  const creditsLimit   = null; // not directly on Usage; shown in side panel if known
  const creditsPerMsg  = activeModel?.credits_per_message ?? null;

  return (
    <div className="flex gap-4 h-[calc(100vh-280px)] min-h-[520px]">

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
          {messages.length === 0 && (
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
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "agent" && (
                <div className="w-7 h-7 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Bot className="w-4 h-4 text-indigo-500" />
                </div>
              )}

              <div className={`flex flex-col gap-1 max-w-[72%] ${msg.role === "user" ? "items-end" : "items-start"}`}>
                <div
                  className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                    msg.role === "user"
                      ? "bg-indigo-600 text-white rounded-br-sm"
                      : "bg-gray-100 text-gray-800 rounded-bl-sm"
                  }`}
                >
                  {msg.content}
                </div>

                {msg.role === "agent" && (
                  <p className="text-[11px] text-gray-400 px-1">
                    {msg.meta.credits_used} crédito{msg.meta.credits_used !== 1 ? "s" : ""}
                    {" · "}
                    {formatDuration(msg.meta.duration_ms)}
                    {" · "}
                    {msg.meta.model.display_name}
                  </p>
                )}
              </div>
            </div>
          ))}

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
                // Auto-grow up to 5 rows
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
            As mensagens não são salvas. Histórico disponível apenas nesta sessão.
          </p>
        </div>
      </div>

      {/* ── Side panel ── */}
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
                <span className="font-medium text-gray-700">{creditsUsed?.toLocaleString("pt-BR")}</span>
              </div>
            </div>
          </div>
        )}

        {/* Knowledge base notice */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-2">
          <h4 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Ferramentas</h4>
          <div className="flex items-start gap-2">
            <Database className="w-3.5 h-3.5 text-gray-300 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs text-gray-400">Base de conhecimento ainda não conectada.</p>
              <p className="text-[11px] text-gray-300 mt-0.5 italic">Sem RAG nesta fase.</p>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <MessageSquare className="w-3.5 h-3.5 text-gray-300 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-gray-400">Nenhuma ferramenta configurada.</p>
          </div>
          <p className="text-[11px] text-gray-300 italic">Disponível na Phase 4</p>
        </div>
      </div>
    </div>
  );
}
