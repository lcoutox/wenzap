"use client";

import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { SaveBar } from "@/components/agents/workspace/SaveBar";
import type {
  GuidedConfig,
  GuidedDoItem,
  GuidedDontItem,
  GuidedInitiative,
  GuidedPosture,
  GuidedRole,
  GuidedWhenNoInfo,
  InstructionsMode,
} from "@/lib/api";

// ── Style helpers ─────────────────────────────────────────────────────────────

const baseInput =
  "w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors";

const disabledInput =
  "w-full bg-nb-bg border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-muted cursor-not-allowed";

const baseSelect =
  "w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors";

// ── Static labels ─────────────────────────────────────────────────────────────

const ROLE_OPTIONS: { value: GuidedRole; label: string }[] = [
  { value: "initial_support", label: "Atendimento inicial" },
  { value: "consultive_sales", label: "Vendas consultivas" },
  { value: "presales_qualification", label: "Pré-vendas / qualificação" },
  { value: "customer_support", label: "Suporte ao cliente" },
  { value: "relationship_postsale", label: "Relacionamento / pós-venda" },
  { value: "reception_triage", label: "Recepção e triagem" },
  { value: "custom", label: "Personalizado" },
];

const POSTURE_OPTIONS: { value: GuidedPosture; label: string; description: string }[] = [
  { value: "consultive", label: "Consultivo", description: "Faz perguntas e recomenda o próximo passo" },
  { value: "direct", label: "Direto", description: "Responde com clareza e sem elaboração desnecessária" },
  { value: "educational", label: "Educativo", description: "Explica conceitos com calma" },
  { value: "welcoming", label: "Acolhedor", description: "Prioriza empatia e linguagem leve" },
  { value: "technical", label: "Técnico", description: "Usa termos técnicos quando necessário" },
];

const INITIATIVE_OPTIONS: { value: GuidedInitiative; label: string }[] = [
  { value: "only_respond", label: "Responder apenas o que foi perguntado" },
  { value: "respond_suggest", label: "Responder e sugerir próximo passo quando fizer sentido" },
  { value: "drive_conversion", label: "Fazer perguntas de qualificação e guiar para conversão" },
];

const WHEN_NO_INFO_OPTIONS: { value: GuidedWhenNoInfo; label: string }[] = [
  { value: "ask_context", label: "Pedir mais contexto ao visitante" },
  { value: "direct_to_team", label: "Conectar com a equipe humana" },
  { value: "knowledge_only", label: "Apenas dizer que não tem a informação" },
];

const DO_ITEMS: { value: GuidedDoItem; label: string }[] = [
  { value: "answer_company_questions", label: "Responder perguntas sobre a empresa" },
  { value: "explain_products", label: "Explicar produtos, serviços ou planos" },
  { value: "qualify_leads", label: "Qualificar leads com perguntas simples" },
  { value: "recommend_catalog", label: "Recomendar itens do catálogo quando relevante" },
  { value: "guide_next_step", label: "Guiar o visitante para o próximo passo" },
  { value: "ask_context", label: "Pedir mais contexto quando a pergunta é vaga" },
  { value: "use_knowledge_base", label: "Consultar a base de conhecimento antes de responder" },
];

const DONT_ITEMS: { value: GuidedDontItem; label: string }[] = [
  { value: "no_fake_prices", label: "Inventar preços, prazos ou políticas" },
  { value: "no_fake_discounts", label: "Prometer descontos não autorizados" },
  { value: "no_guarantee_results", label: "Garantir resultados" },
  { value: "no_fake_integrations", label: "Afirmar integrações que não existem" },
  { value: "no_official_partner_claims", label: "Dizer que é parceiro oficial sem confirmação" },
  { value: "no_sensitive_data", label: "Solicitar dados sensíveis desnecessariamente" },
  { value: "no_out_of_scope", label: "Responder fora do escopo da empresa" },
];

// ── Sub-components ────────────────────────────────────────────────────────────

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
      <label className="block text-sm font-medium text-nb-secondary">{label}</label>
      {children}
      {hint && <p className="text-xs text-nb-muted">{hint}</p>}
    </div>
  );
}

function CheckboxGroup<T extends string>({
  items,
  selected,
  onChange,
  readonly,
}: {
  items: { value: T; label: string }[];
  selected: T[];
  onChange: (v: T[]) => void;
  readonly: boolean;
}) {
  const toggle = (value: T) => {
    if (readonly) return;
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  return (
    <div className="grid grid-cols-1 gap-2">
      {items.map(({ value, label }) => {
        const checked = selected.includes(value);
        return (
          <label
            key={value}
            className={`flex items-start gap-2.5 p-2.5 rounded-lg border cursor-pointer transition-colors text-sm ${
              checked
                ? "border-nb-primary bg-nb-primary/5 text-nb-text"
                : "border-nb-border bg-nb-elevated text-nb-muted hover:border-nb-border-strong"
            } ${readonly ? "opacity-60 cursor-not-allowed" : ""}`}
          >
            <input
              type="checkbox"
              checked={checked}
              onChange={() => toggle(value)}
              disabled={readonly}
              className="mt-0.5 accent-nb-primary"
            />
            <span>{label}</span>
          </label>
        );
      })}
    </div>
  );
}

// ── Mode toggle ───────────────────────────────────────────────────────────────

function ModeToggle({
  mode,
  onChange,
  readonly,
}: {
  mode: InstructionsMode;
  onChange: (m: InstructionsMode) => void;
  readonly: boolean;
}) {
  return (
    <div className="flex gap-2 p-1 bg-nb-bg border border-nb-border rounded-xl w-fit">
      {(["guided", "advanced"] as const).map((m) => (
        <button
          key={m}
          type="button"
          disabled={readonly}
          onClick={() => !readonly && onChange(m)}
          className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            mode === m
              ? "bg-nb-elevated text-nb-text shadow-sm border border-nb-border"
              : "text-nb-muted hover:text-nb-secondary"
          } disabled:cursor-not-allowed`}
        >
          {m === "guided" ? "Guiado" : "Avançado"}
        </button>
      ))}
    </div>
  );
}

// ── Guided form ───────────────────────────────────────────────────────────────

function GuidedForm({
  config,
  onChange,
  readonly,
}: {
  config: GuidedConfig;
  onChange: (c: GuidedConfig) => void;
  readonly: boolean;
}) {
  const upd = (patch: Partial<GuidedConfig>) => onChange({ ...config, ...patch });

  return (
    <div className="space-y-6">
      <AgentFormSection title="Papel do agente" description="Qual é a principal função deste agente?">
        <Field label="Papel">
          <select
            value={config.role ?? ""}
            onChange={(e) => upd({ role: (e.target.value as GuidedRole) || null })}
            disabled={readonly}
            className={readonly ? disabledInput : baseSelect}
          >
            <option value="">Selecione um papel (opcional)</option>
            {ROLE_OPTIONS.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>

        <Field
          label="Objetivo principal"
          hint={`${(config.main_objective ?? "").length} / 500 caracteres`}
        >
          <textarea
            value={config.main_objective ?? ""}
            onChange={(e) => upd({ main_objective: e.target.value || null })}
            rows={3}
            maxLength={500}
            disabled={readonly}
            placeholder="Ex: Ajudar visitantes a entender os planos disponíveis e guiá-los para uma demonstração"
            className={readonly ? disabledInput : baseInput}
          />
        </Field>
      </AgentFormSection>

      <AgentFormSection title="Postura e iniciativa" description="Como o agente deve se comunicar e agir?">
        <Field label="Postura de comunicação">
          <div className="grid grid-cols-1 gap-2">
            {POSTURE_OPTIONS.map(({ value, label, description }) => (
              <label
                key={value}
                className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                  config.posture === value
                    ? "border-nb-primary bg-nb-primary/5"
                    : "border-nb-border bg-nb-elevated hover:border-nb-border-strong"
                } ${readonly ? "opacity-60 cursor-not-allowed" : ""}`}
              >
                <input
                  type="radio"
                  name="posture"
                  value={value}
                  checked={config.posture === value}
                  onChange={() => !readonly && upd({ posture: value })}
                  disabled={readonly}
                  className="mt-0.5 accent-nb-primary"
                />
                <div>
                  <p className="text-sm font-medium text-nb-text">{label}</p>
                  <p className="text-xs text-nb-muted">{description}</p>
                </div>
              </label>
            ))}
          </div>
        </Field>

        <Field label="Nível de iniciativa">
          <select
            value={config.initiative ?? ""}
            onChange={(e) => upd({ initiative: (e.target.value as GuidedInitiative) || null })}
            disabled={readonly}
            className={readonly ? disabledInput : baseSelect}
          >
            <option value="">Selecione (opcional)</option>
            {INITIATIVE_OPTIONS.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Quando não tiver informação suficiente">
          <select
            value={config.when_no_info ?? ""}
            onChange={(e) => upd({ when_no_info: (e.target.value as GuidedWhenNoInfo) || null })}
            disabled={readonly}
            className={readonly ? disabledInput : baseSelect}
          >
            <option value="">Selecione (opcional)</option>
            {WHEN_NO_INFO_OPTIONS.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
      </AgentFormSection>

      <AgentFormSection title="O que o agente deve fazer" description="Selecione as ações permitidas.">
        <CheckboxGroup
          items={DO_ITEMS}
          selected={config.do_items ?? []}
          onChange={(v) => upd({ do_items: v })}
          readonly={readonly}
        />
      </AgentFormSection>

      <AgentFormSection title="O que o agente não deve fazer" description="Selecione as restrições.">
        <CheckboxGroup
          items={DONT_ITEMS}
          selected={config.dont_items ?? []}
          onChange={(v) => upd({ dont_items: v })}
          readonly={readonly}
        />
        <Field
          label="Restrições adicionais (opcional)"
          hint={`${(config.extra_restrictions ?? "").length} / 1000 caracteres`}
        >
          <textarea
            value={config.extra_restrictions ?? ""}
            onChange={(e) => upd({ extra_restrictions: e.target.value || null })}
            rows={3}
            maxLength={1000}
            disabled={readonly}
            placeholder="Ex: Nunca mencionar concorrentes pelo nome"
            className={readonly ? disabledInput : baseInput}
          />
        </Field>
      </AgentFormSection>

      <AgentFormSection
        title="Exemplos de resposta (opcional)"
        description="Mostre ao agente como deve e como não deve responder."
      >
        <Field
          label="Exemplo de boa resposta"
          hint={`${(config.good_response_example ?? "").length} / 2000 caracteres`}
        >
          <textarea
            value={config.good_response_example ?? ""}
            onChange={(e) => upd({ good_response_example: e.target.value || null })}
            rows={4}
            maxLength={2000}
            disabled={readonly}
            placeholder='Ex: "Claro! Nosso plano Starter começa em R$ 99/mês e inclui até 3 agentes. Quer agendar uma demonstração?"'
            className={readonly ? disabledInput : baseInput}
          />
        </Field>
        <Field
          label="Exemplo de resposta a evitar"
          hint={`${(config.bad_response_example ?? "").length} / 2000 caracteres`}
        >
          <textarea
            value={config.bad_response_example ?? ""}
            onChange={(e) => upd({ bad_response_example: e.target.value || null })}
            rows={4}
            maxLength={2000}
            disabled={readonly}
            placeholder='Ex: "Não sei, tente ligar para o suporte."'
            className={readonly ? disabledInput : baseInput}
          />
        </Field>
      </AgentFormSection>
    </div>
  );
}

// ── Advanced form ─────────────────────────────────────────────────────────────

function AdvancedForm({
  advancedPrompt,
  onChange,
  readonly,
}: {
  advancedPrompt: string;
  onChange: (v: string) => void;
  readonly: boolean;
}) {
  return (
    <AgentFormSection
      title="Instruções avançadas"
      description="Escreva as instruções completas do agente em texto livre. Obrigatório para ativar o agente."
    >
      <div className="space-y-1.5">
        <label className="block text-sm font-medium text-nb-secondary">Instruções</label>
        <textarea
          value={advancedPrompt}
          onChange={(e) => onChange(e.target.value)}
          rows={14}
          maxLength={20000}
          disabled={readonly}
          placeholder={
            readonly
              ? ""
              : "Ex: Você é um agente de suporte especializado em SaaS B2B. Responda de forma objetiva, não invente informações e peça para falar com um humano quando não souber responder."
          }
          className={readonly ? disabledInput : baseInput}
        />
        <p className="text-xs text-nb-muted">{advancedPrompt.length} / 20000 caracteres</p>
      </div>
    </AgentFormSection>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ConfigInstrucoes({
  instructionsMode,
  guidedConfig,
  advancedPrompt,
  readonly,
  saving,
  saveError,
  saveSuccess,
  onInstructionsModeChange,
  onGuidedConfigChange,
  onAdvancedPromptChange,
}: {
  instructionsMode: InstructionsMode;
  guidedConfig: GuidedConfig;
  advancedPrompt: string;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onInstructionsModeChange: (m: InstructionsMode) => void;
  onGuidedConfigChange: (c: GuidedConfig) => void;
  onAdvancedPromptChange: (v: string) => void;
}) {
  return (
    <div className="space-y-5">
      {/* Mode selector */}
      <AgentFormSection
        title="Modo de configuração"
        description="Guiado é recomendado para a maioria dos casos. Avançado oferece controle total sobre as instruções."
      >
        <ModeToggle mode={instructionsMode} onChange={onInstructionsModeChange} readonly={readonly} />
        <p className="text-xs text-nb-muted mt-2">
          {instructionsMode === "guided"
            ? "Configure o comportamento do agente com opções pré-definidas."
            : "Escreva as instruções completas do agente em texto livre."}
        </p>
      </AgentFormSection>

      {/* Mode-specific form */}
      {instructionsMode === "guided" ? (
        <GuidedForm config={guidedConfig} onChange={onGuidedConfigChange} readonly={readonly} />
      ) : (
        <AdvancedForm
          advancedPrompt={advancedPrompt}
          onChange={onAdvancedPromptChange}
          readonly={readonly}
        />
      )}

      {!readonly && (
        <SaveBar saving={saving} saveError={saveError} saveSuccess={saveSuccess} />
      )}
    </div>
  );
}
