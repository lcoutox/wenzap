import { Bot, Coins, Cpu, MessageSquare, Send, Sparkles } from "lucide-react";
import { AgentStatusBadge } from "@/components/agents/AgentStatusBadge";
import type { Agent, AiModel } from "@/lib/api";

export function ChatPlaceholder({
  agent,
  activeModel,
}: {
  agent: Agent;
  activeModel: AiModel | null;
}) {
  return (
    <div className="flex gap-0 h-[calc(100vh-280px)] min-h-[480px]">
      {/* Chat area */}
      <div className="flex-1 flex flex-col bg-white rounded-xl border border-gray-200 overflow-hidden">
        {/* Messages area */}
        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
          <div className="w-16 h-16 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-4">
            <Sparkles className="w-8 h-8 text-indigo-400" />
          </div>
          <h3 className="text-base font-semibold text-gray-800 mb-2">
            Agent Playground
          </h3>
          <p className="text-sm text-gray-500 max-w-xs leading-relaxed">
            Teste seu agente em tempo real aqui. O Playground será implementado na próxima fase.
          </p>
          <div className="mt-4 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-indigo-50 border border-indigo-200 text-xs font-medium text-indigo-600">
            <Sparkles className="w-3 h-3" />
            Em breve — Phase 3
          </div>
        </div>

        {/* Input bar (disabled) */}
        <div className="border-t border-gray-100 p-4 bg-gray-50/50">
          <div className="flex items-end gap-3">
            <div className="flex-1 relative">
              <input
                type="text"
                disabled
                placeholder="O Playground ainda não está disponível…"
                className="w-full px-4 py-2.5 pr-12 rounded-lg border border-gray-200 bg-gray-100 text-sm text-gray-400 cursor-not-allowed placeholder-gray-400"
              />
            </div>
            <button
              type="button"
              disabled
              className="p-2.5 rounded-lg bg-gray-200 text-gray-400 cursor-not-allowed"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
          <p className="mt-2 text-xs text-center text-gray-400">
            Envio de mensagens disponível na Phase 3 — Playground
          </p>
        </div>
      </div>

      {/* Side panel */}
      <div className="w-64 flex-shrink-0 ml-4 space-y-3">
        {/* Agent info */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Agente</h4>
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
        {activeModel && (
          <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-2">
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Modelo</h4>
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <span className="text-sm text-gray-700 truncate">{activeModel.display_name}</span>
            </div>
            {activeModel.credits_per_message > 0 && (
              <div className="flex items-center gap-2">
                <Coins className="w-4 h-4 text-amber-500 flex-shrink-0" />
                <span className="text-sm text-amber-600">
                  {activeModel.credits_per_message} crédito{activeModel.credits_per_message !== 1 ? "s" : ""}/msg
                </span>
              </div>
            )}
          </div>
        )}

        {/* Future tools */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-2">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Ferramentas</h4>
          <div className="flex items-center gap-2 text-gray-400">
            <MessageSquare className="w-4 h-4" />
            <span className="text-xs">Nenhuma ferramenta configurada</span>
          </div>
          <p className="text-xs text-gray-300 italic">Disponível na Phase 4</p>
        </div>
      </div>
    </div>
  );
}
