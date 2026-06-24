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
      <div className="flex-1 flex flex-col bg-nb-panel rounded-2xl border border-nb-border overflow-hidden">
        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
          <div className="w-16 h-16 rounded-2xl bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center mb-4">
            <Sparkles className="w-8 h-8 text-nb-primary" />
          </div>
          <h3 className="text-base font-semibold text-nb-secondary mb-2">Agent Playground</h3>
          <p className="text-sm text-nb-muted max-w-xs leading-relaxed">
            Teste seu agente em tempo real aqui. O Playground será implementado na próxima fase.
          </p>
          <div className="mt-4 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-nb-primary-bg border border-nb-primary/20 text-xs font-medium text-nb-primary-strong">
            <Sparkles className="w-3 h-3" />
            Em breve — Phase 3
          </div>
        </div>

        <div className="border-t border-nb-border p-4 bg-nb-surface">
          <div className="flex items-end gap-3">
            <input
              type="text"
              disabled
              placeholder="O Playground ainda não está disponível…"
              className="flex-1 px-4 py-2.5 rounded-xl border border-nb-border bg-nb-bg text-sm text-nb-muted cursor-not-allowed placeholder-nb-muted"
            />
            <button type="button" disabled className="p-2.5 rounded-xl bg-nb-elevated text-nb-muted cursor-not-allowed">
              <Send className="w-4 h-4" />
            </button>
          </div>
          <p className="mt-2 text-xs text-center text-nb-muted">
            Envio de mensagens disponível na Phase 3 — Playground
          </p>
        </div>
      </div>

      {/* Side panel */}
      <div className="w-64 flex-shrink-0 ml-4 space-y-3">
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

        {activeModel && (
          <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 space-y-2">
            <h4 className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Modelo</h4>
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-nb-muted flex-shrink-0" />
              <span className="text-sm text-nb-secondary truncate">{activeModel.display_name}</span>
            </div>
            {activeModel.credits_per_message > 0 && (
              <div className="flex items-center gap-2">
                <Coins className="w-4 h-4 text-nb-warning flex-shrink-0" />
                <span className="text-sm text-nb-warning">
                  {activeModel.credits_per_message} crédito{activeModel.credits_per_message !== 1 ? "s" : ""}/msg
                </span>
              </div>
            )}
          </div>
        )}

        <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 space-y-2">
          <h4 className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Ferramentas</h4>
          <div className="flex items-center gap-2 text-nb-muted">
            <MessageSquare className="w-4 h-4" />
            <span className="text-xs">Nenhuma ferramenta configurada</span>
          </div>
          <p className="text-xs text-nb-muted/40 italic">Disponível na Phase 4</p>
        </div>
      </div>
    </div>
  );
}
