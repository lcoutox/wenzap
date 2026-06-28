export type AgentTypeId =
  | "support"
  | "sales"
  | "tech"
  | "scheduling"
  | "collections"
  | "blank";

export type ToneOption =
  | "Profissional"
  | "Simpático"
  | "Direto ao ponto"
  | "Consultivo"
  | "Descontraído"
  | "Técnico";

export type CreativityLevel = "precise" | "balanced" | "creative";

export interface WizardState {
  // Step 1
  agentType: AgentTypeId | null;
  // Step 2
  name: string;
  description: string;
  // Step 3
  tones: ToneOption[];
  rules: string[];
  avoidText: string;
  additionalInstructions: string;
  // Step 4
  selectedKbIds: string[];
  // Step 5
  aiModelId: string | null;
  creativity: CreativityLevel;
}

export const INITIAL_WIZARD_STATE: WizardState = {
  agentType: null,
  name: "",
  description: "",
  tones: [],
  rules: [],
  avoidText: "",
  additionalInstructions: "",
  selectedKbIds: [],
  aiModelId: null,
  creativity: "balanced",
};

export const CREATIVITY_TEMPERATURE: Record<CreativityLevel, number> = {
  precise: 0.2,
  balanced: 0.7,
  creative: 0.9,
};

export const ALL_RULES: { id: string; label: string }[] = [
  { id: "objective",     label: "Responder de forma objetiva" },
  { id: "ask",          label: "Fazer perguntas quando faltar informação" },
  { id: "no_invent",   label: "Não inventar respostas" },
  { id: "kb_only",     label: "Usar apenas informações conhecidas" },
  { id: "next_step",   label: "Orientar o cliente para o próximo passo" },
  { id: "human",       label: "Pedir ajuda humana quando não souber responder" },
];

export const AGENT_TYPE_DEFAULTS: Record<
  AgentTypeId,
  { descriptionHint: string; rules: string[]; tones: ToneOption[] }
> = {
  support: {
    descriptionHint:
      "Responde dúvidas frequentes, orienta clientes e usa o conhecimento da empresa.",
    rules: ["objective", "no_invent", "kb_only", "human"],
    tones: ["Profissional", "Simpático"],
  },
  sales: {
    descriptionHint:
      "Entende o interesse do cliente, faz perguntas de qualificação e direciona oportunidades.",
    rules: ["ask", "next_step", "no_invent"],
    tones: ["Consultivo", "Simpático"],
  },
  tech: {
    descriptionHint:
      "Ajuda usuários a resolver problemas, seguir procedimentos e encontrar respostas.",
    rules: ["objective", "no_invent", "kb_only", "human"],
    tones: ["Técnico", "Direto ao ponto"],
  },
  scheduling: {
    descriptionHint:
      "Ajuda clientes a consultar horários, tirar dúvidas e avançar para um agendamento.",
    rules: ["ask", "objective", "next_step"],
    tones: ["Simpático", "Profissional"],
  },
  collections: {
    descriptionHint:
      "Envia lembretes e conduz conversas de acompanhamento com tom profissional.",
    rules: ["objective", "no_invent", "next_step"],
    tones: ["Profissional", "Direto ao ponto"],
  },
  blank: {
    descriptionHint: "",
    rules: [],
    tones: [],
  },
};
