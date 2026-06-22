import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { SaveBar } from "@/components/agents/workspace/SaveBar";

const baseInput =
  "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent";
const disabledInput =
  "w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-400 bg-gray-50 cursor-not-allowed";

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      {children}
      {hint && <p className="text-xs text-gray-400">{hint}</p>}
    </div>
  );
}

export function ConfigPrompt({
  systemPrompt,
  persona,
  readonly,
  saving,
  saveError,
  saveSuccess,
  onSystemPromptChange,
  onPersonaChange,
}: {
  systemPrompt: string;
  persona: string;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onSystemPromptChange: (v: string) => void;
  onPersonaChange: (v: string) => void;
}) {
  return (
    <div className="space-y-5">
      <AgentFormSection
        title="System Prompt"
        description="Instrução base que define o comportamento do agente. Obrigatório para ativar."
      >
        <Field label="Prompt" hint={`${systemPrompt.length} / 8000 caracteres`}>
          <textarea
            value={systemPrompt}
            onChange={(e) => onSystemPromptChange(e.target.value)}
            rows={10}
            maxLength={8000}
            disabled={readonly}
            placeholder={
              readonly ? "" : "Você é um agente de suporte da empresa Acme. Seu objetivo é ajudar clientes a resolver problemas com nossos produtos de forma rápida e amigável..."
            }
            className={readonly ? disabledInput : baseInput}
          />
        </Field>
      </AgentFormSection>

      <AgentFormSection
        title="Persona e Tom"
        description="Define a personalidade e o estilo de comunicação do agente."
      >
        <Field label="Persona" hint={`${persona.length} / 1000 caracteres`}>
          <textarea
            value={persona}
            onChange={(e) => onPersonaChange(e.target.value)}
            rows={4}
            maxLength={1000}
            disabled={readonly}
            placeholder={readonly ? "" : "Comunicativo, empático, direto ao ponto. Usa linguagem simples e evita jargões técnicos."}
            className={readonly ? disabledInput : baseInput}
          />
        </Field>
      </AgentFormSection>

      {!readonly && (
        <SaveBar saving={saving} saveError={saveError} saveSuccess={saveSuccess} />
      )}
    </div>
  );
}
