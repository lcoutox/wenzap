"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Send, Loader2, AlertCircle, Bot } from "lucide-react";
import { api } from "@/lib/api";
const DEFAULT_SUGGESTIONS = [
  "Olá, como você pode me ajudar?",
  "O que você sabe responder?",
  "Quais informações você usa?",
];

function SummaryRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex gap-3 py-2 border-b border-nb-border last:border-0">
      <span className="w-28 flex-shrink-0 text-xs font-semibold text-nb-muted uppercase tracking-wide">
        {label}
      </span>
      <span className="text-sm text-nb-secondary">{value}</span>
    </div>
  );
}

export function StepSuccess({
  agentId,
  agentName,
  description,
  modelDisplayName,
  connectedKbNames,
  kbWarning,
  needsPromptSetup = false,
}: {
  agentId: string;
  agentName: string;
  description: string;
  modelDisplayName: string | null;
  connectedKbNames: string[];
  kbWarning: boolean;
  agentType?: unknown;
  /** True for agents created "from scratch" — no prompt yet, quick-test would just fail. */
  needsPromptSetup?: boolean;
}) {
  const router = useRouter();

  const [testInput,    setTestInput]    = useState("");
  const [testReply,    setTestReply]    = useState<string | null>(null);
  const [testLoading,  setTestLoading]  = useState(false);
  const [testError,    setTestError]    = useState<string | null>(null);
  const [sessionId,    setSessionId]    = useState<string | undefined>(undefined);

  const suggestions = DEFAULT_SUGGESTIONS;

  async function sendTest(message: string) {
    if (!message.trim() || testLoading) return;
    setTestError(null);
    setTestReply(null);
    setTestLoading(true);
    try {
      const res = await api.agents.test(agentId, message.trim(), sessionId);
      setTestReply(res.reply);
      setSessionId(res.session_id);
    } catch {
      setTestError(
        "Não foi possível testar o agente agora. Você pode tentar novamente na tela do agente."
      );
    } finally {
      setTestLoading(false);
    }
  }

  function handleSuggestion(s: string) {
    setTestInput(s);
    sendTest(s);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    sendTest(testInput);
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-nb-success/10 border border-nb-success/20 flex items-center justify-center flex-shrink-0">
          <CheckCircle2 className="w-5 h-5 text-nb-success" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-nb-text">Agente criado com sucesso</h2>
          <p className="text-sm text-nb-muted mt-0.5">
            {needsPromptSetup
              ? "Falta um passo: escreva o prompt do agente antes de testar ou ativar."
              : "Seu agente já está configurado. Faça um teste rápido antes de continuar."}
          </p>
        </div>
      </div>

      {/* Prompt setup warning (agents created "from scratch") */}
      {needsPromptSetup && (
        <div className="flex items-start gap-2.5 p-3.5 bg-nb-warning/10 border border-nb-warning/20 rounded-xl">
          <AlertCircle className="w-4 h-4 text-nb-warning flex-shrink-0 mt-0.5" />
          <p className="text-sm text-nb-warning">
            Você escolheu começar do zero, então o agente ainda não tem instruções — o teste
            rápido e a ativação só funcionam depois de preencher o prompt em
            Configurações → Instruções.
          </p>
        </div>
      )}

      {/* KB warning */}
      {kbWarning && (
        <div className="flex items-start gap-2.5 p-3.5 bg-nb-warning/10 border border-nb-warning/20 rounded-xl">
          <AlertCircle className="w-4 h-4 text-nb-warning flex-shrink-0 mt-0.5" />
          <p className="text-sm text-nb-warning">
            O agente foi criado, mas algumas bases não puderam ser conectadas. Você pode
            ajustar isso depois na aba Conhecimento.
          </p>
        </div>
      )}

      {/* Summary */}
      <div className="bg-nb-elevated border border-nb-border rounded-2xl px-4 divide-y divide-nb-border">
        <SummaryRow label="Nome" value={agentName} />
        {description && <SummaryRow label="Objetivo" value={description} />}
        {modelDisplayName && <SummaryRow label="Modelo" value={modelDisplayName} />}
        {connectedKbNames.length > 0 && (
          <SummaryRow
            label="Bases"
            value={connectedKbNames.join(", ")}
          />
        )}
      </div>

      {/* Quick test — skipped for agents with no prompt yet, it would just fail */}
      {!needsPromptSetup && (
      <div className="space-y-3">
        <p className="text-sm font-medium text-nb-secondary">Teste seu agente</p>

        {/* Suggestions */}
        <div className="flex flex-wrap gap-2">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => handleSuggestion(s)}
              disabled={testLoading}
              className="px-3 py-1.5 text-xs bg-nb-elevated border border-nb-border text-nb-muted rounded-lg hover:border-nb-border-strong hover:text-nb-secondary transition-colors disabled:opacity-40"
            >
              {s}
            </button>
          ))}
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={testInput}
            onChange={(e) => setTestInput(e.target.value)}
            placeholder="Ex: Olá, gostaria de saber como vocês podem me ajudar."
            disabled={testLoading}
            className="flex-1 bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={testLoading || !testInput.trim()}
            className="flex items-center gap-1.5 px-4 py-2 bg-nb-primary text-white text-sm font-medium rounded-xl hover:bg-nb-primary-strong disabled:opacity-40 transition-colors"
          >
            {testLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
            {testLoading ? "" : "Enviar"}
          </button>
        </form>

        {/* Test reply */}
        {testLoading && (
          <div className="flex items-center gap-2 text-sm text-nb-muted py-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            O agente está respondendo…
          </div>
        )}

        {testReply && (
          <div className="flex items-start gap-3 p-4 bg-nb-elevated border border-nb-border rounded-2xl">
            <div className="w-7 h-7 rounded-lg bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4 text-nb-primary-strong" />
            </div>
            <p className="text-sm text-nb-secondary leading-relaxed whitespace-pre-wrap">
              {testReply}
            </p>
          </div>
        )}

        {testError && (
          <p className="text-sm text-nb-danger">{testError}</p>
        )}
      </div>
      )}

      {/* Final actions */}
      <div className="flex flex-wrap items-center gap-3 pt-2">
        <button
          type="button"
          onClick={() =>
            router.push(
              needsPromptSetup
                ? `/dashboard/agents/${agentId}?tab=settings&configTab=instrucoes`
                : `/dashboard/agents/${agentId}`
            )
          }
          className="px-5 py-2 bg-nb-primary text-white text-sm font-medium rounded-xl hover:bg-nb-primary-strong transition-colors"
        >
          {needsPromptSetup ? "Configurar prompt" : "Abrir agente"}
        </button>
        <button
          type="button"
          onClick={() => router.push("/dashboard/agents/new")}
          className="px-4 py-2 text-sm font-medium text-nb-muted hover:text-nb-secondary transition-colors"
        >
          Criar outro agente
        </button>
      </div>
    </div>
  );
}
