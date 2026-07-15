"use client";

import { useState } from "react";
import type {
  GuidedConfig,
  GuidedDoItem,
  GuidedDontItem,
  GuidedInitiative,
  GuidedPosture,
  GuidedRole,
  GuidedWhenNoInfo,
  InstructionsMode,
  LanguageMode,
  ResponseStyle,
} from "@/lib/api";
import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { SaveBar } from "@/components/agents/workspace/SaveBar";

// ── Static option maps ────────────────────────────────────────────────────────

const ROLE_OPTIONS: { value: GuidedRole; label: string; description: string }[] = [
  { value: "initial_support",        label: "Atendimento inicial",       description: "Recebe visitantes e orienta para o caminho certo." },
  { value: "consultive_sales",       label: "Vendas consultivas",        description: "Entende a necessidade e guia sem ser agressivo." },
  { value: "presales_qualification", label: "Pré-vendas / qualificação", description: "Identifica o perfil do lead antes de encaminhar." },
  { value: "customer_support",       label: "Suporte ao cliente",        description: "Ajuda clientes com dúvidas usando a base de conhecimento." },
  { value: "relationship_postsale",  label: "Relacionamento / pós-venda", description: "Reforça boas práticas e acompanha uso da solução." },
  { value: "reception_triage",       label: "Recepção e triagem",        description: "Direciona rapidamente para o melhor caminho." },
  { value: "custom",                 label: "Personalizado",             description: "Configure o objetivo manualmente abaixo." },
];

const POSTURE_OPTIONS: { value: GuidedPosture; label: string }[] = [
  { value: "consultive",  label: "Consultivo — faz perguntas e recomenda" },
  { value: "direct",      label: "Direto — responde com clareza e sem rodeios" },
  { value: "educational", label: "Educativo — explica com calma" },
  { value: "welcoming",   label: "Acolhedor — prioriza empatia" },
  { value: "technical",   label: "Técnico — usa termos técnicos quando necessário" },
];

const INITIATIVE_OPTIONS: { value: GuidedInitiative; label: string; description: string }[] = [
  { value: "only_respond",     label: "Apenas responder",                    description: "Responde o que foi perguntado, sem sugerir próximos passos." },
  { value: "respond_suggest",  label: "Responder e sugerir",                 description: "Após responder, sugere um próximo passo quando faz sentido." },
  { value: "drive_conversion", label: "Conduzir ativamente para conversão",  description: "Faz perguntas de qualificação e guia para ação." },
];

const WHEN_NO_INFO_OPTIONS: { value: GuidedWhenNoInfo; label: string }[] = [
  { value: "ask_context",    label: "Dizer que não tem informação suficiente e pedir mais contexto" },
  { value: "direct_to_team", label: "Orientar o visitante a falar com a equipe" },
  { value: "knowledge_only", label: "Responder apenas com o que estiver disponível, sem inventar" },
];

const DO_ITEMS: { value: GuidedDoItem; label: string }[] = [
  { value: "answer_company_questions", label: "Responder dúvidas sobre a empresa" },
  { value: "explain_products",         label: "Explicar produtos, serviços ou planos cadastrados" },
  { value: "qualify_leads",            label: "Qualificar interessados com perguntas simples" },
  { value: "recommend_catalog",        label: "Recomendar opções do Catálogo quando relevante" },
  { value: "guide_next_step",          label: "Orientar o visitante para o próximo passo" },
  { value: "ask_context",              label: "Pedir mais contexto quando a pergunta estiver vaga" },
  { value: "use_knowledge_base",       label: "Usar a Base de Conhecimento antes de responder" },
];

const DONT_ITEMS: { value: GuidedDontItem; label: string }[] = [
  { value: "no_fake_prices",             label: "Não inventar preços, prazos ou políticas" },
  { value: "no_fake_discounts",          label: "Não prometer descontos ou condições não informadas" },
  { value: "no_guarantee_results",       label: "Não garantir resultados" },
  { value: "no_fake_integrations",       label: "Não afirmar integrações que não estão disponíveis" },
  { value: "no_official_partner_claims", label: "Não dizer que é parceiro oficial sem confirmação" },
  { value: "no_sensitive_data",          label: "Não pedir dados sensíveis sem necessidade" },
  { value: "no_out_of_scope",            label: "Não responder fora do escopo da empresa" },
];

const RESPONSE_STYLE_OPTIONS: { value: ResponseStyle; label: string; description: string }[] = [
  { value: "concise",  label: "Objetivo",    description: "Respostas curtas e diretas. Ideal para widget e WhatsApp." },
  { value: "balanced", label: "Equilibrado", description: "Respostas claras com contexto suficiente, sem excesso de detalhe." },
  { value: "detailed", label: "Detalhado",   description: "Respostas mais completas para suporte aprofundado." },
];

const LANGUAGE_OPTIONS: { value: LanguageMode; label: string }[] = [
  { value: "auto", label: "Automático — responde no idioma do usuário" },
  { value: "pt",   label: "Português (Brasil)" },
  { value: "en",   label: "Inglês" },
  { value: "es",   label: "Espanhol" },
];

// ── Style helpers ─────────────────────────────────────────────────────────────

const baseInput =
  "w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors";
const disabledInput =
  "w-full bg-nb-bg border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-muted cursor-not-allowed";
const baseSelect =
  "w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors";
const disabledSelect =
  "w-full bg-nb-bg border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-muted cursor-not-allowed";

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

function CheckboxList<T extends string>({
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
    onChange(
      selected.includes(value)
        ? selected.filter((v) => v !== value)
        : [...selected, value]
    );
  };

  return (
    <div className="grid grid-cols-1 gap-1.5">
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

function CustomItemList({
  items,
  onChange,
  placeholder,
  readonly,
  addLabel,
}: {
  items: string[];
  onChange: (v: string[]) => void;
  placeholder: string;
  readonly: boolean;
  addLabel: string;
}) {
  const [draft, setDraft] = useState("");

  function add() {
    const trimmed = draft.trim();
    if (!trimmed || readonly) return;
    onChange([...items, trimmed]);
    setDraft("");
  }

  function remove(idx: number) {
    onChange(items.filter((_, i) => i !== idx));
  }

  return (
    <div className="space-y-2">
      {items.map((item, idx) => (
        <div key={idx} className="flex items-center gap-2 p-2 rounded-lg border border-nb-border bg-nb-elevated text-sm text-nb-text">
          <span className="flex-1 text-nb-secondary">— {item}</span>
          {!readonly && (
            <button
              type="button"
              onClick={() => remove(idx)}
              className="text-nb-muted hover:text-nb-danger text-xs px-1"
            >
              ✕
            </button>
          )}
        </div>
      ))}
      {!readonly && (
        <div className="flex gap-2">
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())}
            placeholder={placeholder}
            maxLength={500}
            className={baseInput + " flex-1"}
          />
          <button
            type="button"
            onClick={add}
            disabled={!draft.trim()}
            className="px-3 py-2 rounded-xl text-sm border border-nb-border text-nb-secondary hover:border-nb-primary hover:text-nb-primary disabled:opacity-40 transition-colors"
          >
            {addLabel}
          </button>
        </div>
      )}
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
      {/* Seção 1 — Papel e objetivo */}
      <AgentFormSection title="1. Papel e objetivo" description="Qual é a principal função deste agente?">
        <Field label="Função principal">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {ROLE_OPTIONS.map(({ value, label, description }) => {
              const active = config.role === value;
              return (
                <button
                  key={value}
                  type="button"
                  disabled={readonly}
                  onClick={() => !readonly && upd({ role: value })}
                  className={`text-left rounded-xl border p-3 transition-colors ${
                    active
                      ? "border-nb-primary bg-nb-primary/5 ring-1 ring-nb-primary/30"
                      : "border-nb-border bg-nb-elevated hover:border-nb-border-strong"
                  } ${readonly ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                >
                  <p className={`text-sm font-semibold ${active ? "text-nb-primary-strong" : "text-nb-text"}`}>{label}</p>
                  <p className="text-xs text-nb-muted mt-0.5 leading-relaxed">{description}</p>
                </button>
              );
            })}
          </div>
        </Field>

        <Field label="Objetivo principal" hint={`${(config.main_objective ?? "").length} / 500 caracteres`}>
          <input
            type="text"
            value={config.main_objective ?? ""}
            maxLength={500}
            disabled={readonly}
            placeholder="Ex: qualificar interessados e explicar os planos do Wenzap"
            onChange={(e) => upd({ main_objective: e.target.value || null })}
            className={readonly ? disabledInput : baseInput}
          />
        </Field>
      </AgentFormSection>

      {/* Seção 2 — Quando não souber */}
      <AgentFormSection title="2. Quando não souber" description="O que o agente deve fazer quando não tiver informação suficiente?">
        <select
          value={config.when_no_info ?? ""}
          disabled={readonly}
          onChange={(e) => upd({ when_no_info: (e.target.value as GuidedWhenNoInfo) || null })}
          className={readonly ? disabledSelect : baseSelect}
        >
          <option value="">Selecione (opcional)</option>
          {WHEN_NO_INFO_OPTIONS.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </AgentFormSection>

      {/* Seção 3 — Estilo de conversa */}
      <AgentFormSection title="3. Estilo de conversa" description="Como o agente deve se comunicar?">
        <Field label="Postura do agente">
          <select
            value={config.posture ?? ""}
            disabled={readonly}
            onChange={(e) => upd({ posture: (e.target.value as GuidedPosture) || null })}
            className={readonly ? disabledSelect : baseSelect}
          >
            <option value="">Selecione (opcional)</option>
            {POSTURE_OPTIONS.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </Field>

        <Field label="Nível de iniciativa">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {INITIATIVE_OPTIONS.map(({ value, label, description }) => {
              const active = config.initiative === value;
              return (
                <button
                  key={value}
                  type="button"
                  disabled={readonly}
                  onClick={() => !readonly && upd({ initiative: value })}
                  className={`text-left rounded-xl border p-3 transition-colors ${
                    active
                      ? "border-nb-primary bg-nb-primary/5 ring-1 ring-nb-primary/30"
                      : "border-nb-border bg-nb-elevated hover:border-nb-border-strong"
                  } ${readonly ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                >
                  <p className={`text-sm font-semibold ${active ? "text-nb-primary-strong" : "text-nb-text"}`}>{label}</p>
                  <p className="text-xs text-nb-muted mt-0.5">{description}</p>
                </button>
              );
            })}
          </div>
        </Field>
      </AgentFormSection>

      {/* Seção 4 — Regras de atuação */}
      <AgentFormSection title="4. Regras de atuação" description="O que o agente deve e não deve fazer.">
        <div className="space-y-4">
          <Field label="O que o agente deve fazer">
            <CheckboxList
              items={DO_ITEMS}
              selected={config.do_items ?? []}
              onChange={(v) => upd({ do_items: v })}
              readonly={readonly}
            />
            <div className="mt-2">
              <CustomItemList
                items={config.custom_should_do ?? []}
                onChange={(v) => upd({ custom_should_do: v })}
                placeholder="Ex: Sempre perguntar o tamanho da empresa antes de recomendar um plano"
                readonly={readonly}
                addLabel="+ Adicionar regra"
              />
            </div>
          </Field>

          <Field label="O que o agente não deve fazer">
            <CheckboxList
              items={DONT_ITEMS}
              selected={config.dont_items ?? []}
              onChange={(v) => upd({ dont_items: v })}
              readonly={readonly}
            />
            <div className="mt-2">
              <CustomItemList
                items={config.custom_should_not_do ?? []}
                onChange={(v) => upd({ custom_should_not_do: v })}
                placeholder="Ex: Não mencionar concorrentes, a menos que o visitante pergunte diretamente"
                readonly={readonly}
                addLabel="+ Adicionar restrição"
              />
            </div>
          </Field>
        </div>
      </AgentFormSection>

      {/* Seção 5 — Exemplos */}
      <AgentFormSection title="5. Exemplos (opcional)" description="Mostre ao agente como deve e como não deve responder.">
        <Field label="Exemplo de boa resposta" hint={`${(config.good_response_example ?? "").length} / 2000 caracteres`}>
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
        <Field label="Exemplo de resposta a evitar" hint={`${(config.bad_response_example ?? "").length} / 2000 caracteres`}>
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
      description="Escreva as instruções completas do agente em texto livre."
    >
      <div className="mb-3 p-3 bg-nb-elevated border border-nb-border rounded-xl text-xs text-nb-muted leading-relaxed">
        No modo avançado, suas instruções substituem o modo guiado. As regras internas de segurança, conhecimento, ferramentas e limites da plataforma continuam sendo aplicadas pelo Wenzap.
      </div>
      <div className="space-y-1.5">
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

// ── Reply delay options ───────────────────────────────────────────────────────

const REPLY_DELAY_OPTIONS: { value: number; label: string; recommended?: boolean }[] = [
  { value: 0,  label: "Imediato" },
  { value: 3,  label: "3 segundos" },
  { value: 5,  label: "5 segundos", recommended: true },
  { value: 8,  label: "8 segundos" },
  { value: 15, label: "15 segundos" },
];

// ── Main component ────────────────────────────────────────────────────────────

export function ConfigComportamento({
  instructionsMode,
  guidedConfig,
  advancedPrompt,
  responseStyle,
  languageMode,
  replyDelaySeconds,
  readonly,
  saving,
  saveError,
  saveSuccess,
  onInstructionsModeChange,
  onGuidedConfigChange,
  onAdvancedPromptChange,
  onResponseStyleChange,
  onLanguageModeChange,
  onReplyDelaySecondsChange,
}: {
  instructionsMode: InstructionsMode;
  guidedConfig: GuidedConfig;
  advancedPrompt: string;
  responseStyle: ResponseStyle;
  languageMode: LanguageMode;
  replyDelaySeconds: number;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onInstructionsModeChange: (m: InstructionsMode) => void;
  onGuidedConfigChange: (c: GuidedConfig) => void;
  onAdvancedPromptChange: (v: string) => void;
  onResponseStyleChange: (v: ResponseStyle) => void;
  onLanguageModeChange: (v: LanguageMode) => void;
  onReplyDelaySecondsChange: (v: number) => void;
}) {
  return (
    <div className="space-y-6">
      {/* Estilo de resposta */}
      <AgentFormSection
        title="Estilo de resposta"
        description="Define o tamanho e a profundidade das respostas geradas pelo agente."
      >
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {RESPONSE_STYLE_OPTIONS.map(({ value, label, description }) => {
            const active = responseStyle === value;
            return (
              <button
                key={value}
                type="button"
                disabled={readonly}
                onClick={() => !readonly && onResponseStyleChange(value)}
                className={`text-left rounded-xl border p-4 transition-colors ${
                  active
                    ? "border-nb-primary bg-nb-primary/5 ring-1 ring-nb-primary/30"
                    : "border-nb-border bg-nb-elevated hover:border-nb-border-strong"
                } ${readonly ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
              >
                <p className={`text-sm font-semibold mb-1 ${active ? "text-nb-primary-strong" : "text-nb-text"}`}>{label}</p>
                <p className="text-xs text-nb-muted leading-relaxed">{description}</p>
              </button>
            );
          })}
        </div>
      </AgentFormSection>

      {/* Idioma */}
      <AgentFormSection
        title="Idioma"
        description="Define em qual idioma o agente responde, independente do idioma da pergunta."
      >
        <select
          value={languageMode}
          disabled={readonly}
          onChange={(e) => onLanguageModeChange(e.target.value as LanguageMode)}
          className={readonly ? disabledSelect : baseSelect}
        >
          {LANGUAGE_OPTIONS.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </AgentFormSection>

      {/* Tempo de resposta */}
      <AgentFormSection
        title="Tempo de resposta"
        description="O agente espera alguns segundos após a última mensagem do cliente antes de responder. Isso evita respostas quebradas quando o cliente envia várias mensagens seguidas."
      >
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          {REPLY_DELAY_OPTIONS.map(({ value, label, recommended }) => {
            const active = replyDelaySeconds === value;
            return (
              <button
                key={value}
                type="button"
                disabled={readonly}
                onClick={() => !readonly && onReplyDelaySecondsChange(value)}
                className={`
                  relative text-left rounded-xl border p-3 transition-all text-sm
                  ${readonly ? "cursor-not-allowed opacity-60" : "cursor-pointer"}
                  ${active
                    ? "border-nb-primary bg-nb-primary-bg/50 ring-1 ring-nb-primary/40"
                    : "border-nb-border bg-nb-elevated hover:border-nb-border-strong"}
                `}
              >
                <span className={`font-medium ${active ? "text-nb-primary-strong" : "text-nb-text"}`}>
                  {label}
                </span>
                {recommended && (
                  <span className="block text-[10px] text-nb-primary mt-0.5">Recomendado</span>
                )}
              </button>
            );
          })}
        </div>
        {replyDelaySeconds === 0 && (
          <p className="text-xs text-nb-muted mt-2">
            Pode responder mais rápido, mas pode gerar respostas antes do cliente terminar de digitar.
          </p>
        )}
      </AgentFormSection>

      {/* Modo de instruções */}
      <AgentFormSection
        title="Modo de configuração"
        description="Guiado é recomendado para a maioria dos casos. Avançado oferece controle total sobre as instruções."
      >
        <div className="flex gap-2 p-1 bg-nb-bg border border-nb-border rounded-xl w-fit">
          {(["guided", "advanced"] as const).map((m) => (
            <button
              key={m}
              type="button"
              disabled={readonly}
              onClick={() => !readonly && onInstructionsModeChange(m)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                instructionsMode === m
                  ? "bg-nb-elevated text-nb-text shadow-sm border border-nb-border"
                  : "text-nb-muted hover:text-nb-secondary"
              } disabled:cursor-not-allowed`}
            >
              {m === "guided" ? "Guiado" : "Avançado"}
            </button>
          ))}
        </div>
        <p className="text-xs text-nb-muted mt-2">
          {instructionsMode === "guided"
            ? "Configure o comportamento com opções pré-definidas."
            : "Escreva as instruções completas do agente em texto livre."}
        </p>
      </AgentFormSection>

      {/* Mode-specific form */}
      {instructionsMode === "guided" ? (
        <GuidedForm config={guidedConfig} onChange={onGuidedConfigChange} readonly={readonly} />
      ) : (
        <AdvancedForm advancedPrompt={advancedPrompt} onChange={onAdvancedPromptChange} readonly={readonly} />
      )}

      {!readonly && (
        <SaveBar saving={saving} saveError={saveError} saveSuccess={saveSuccess} />
      )}
    </div>
  );
}
