import type { GuidedConfig } from "@/lib/api";

export type TemplateId =
  | "customer_support"
  | "sales_qualification"
  | "faq"
  | "onboarding"
  | "collections"
  | "internal_assistant"
  | "blank";

export interface AgentTemplate {
  id: TemplateId;
  label: string;
  tagline: string;
  description: string;
  icon: string;
  guidedConfig: GuidedConfig;
}

export const AGENT_TEMPLATES: AgentTemplate[] = [
  {
    id: "customer_support",
    label: "Suporte ao Cliente",
    tagline: "Responde dúvidas com base no conhecimento da empresa",
    description: "Atende clientes, responde perguntas frequentes e orienta para o próximo passo sem inventar informações.",
    icon: "🎧",
    guidedConfig: {
      role: "customer_support",
      main_objective: "Responder dúvidas de clientes com clareza, usando a base de conhecimento da empresa.",
      posture: "welcoming",
      initiative: "respond_suggest",
      when_no_info: "direct_to_team",
      do_items: ["answer_company_questions", "explain_products", "use_knowledge_base", "guide_next_step"],
      custom_should_do: [],
      dont_items: ["no_fake_prices", "no_guarantee_results", "no_out_of_scope"],
      custom_should_not_do: [],
      extra_restrictions: null,
      good_response_example: null,
      bad_response_example: null,
    },
  },
  {
    id: "sales_qualification",
    label: "Vendas e Qualificação",
    tagline: "Qualifica leads e conduz para conversão",
    description: "Entende o perfil do visitante, faz perguntas de qualificação e guia para o próximo passo comercial.",
    icon: "📈",
    guidedConfig: {
      role: "consultive_sales",
      main_objective: "Qualificar interessados, entender a necessidade e orientar para o próximo passo comercial.",
      posture: "consultive",
      initiative: "drive_conversion",
      when_no_info: "ask_context",
      do_items: ["qualify_leads", "explain_products", "guide_next_step", "recommend_catalog"],
      custom_should_do: [],
      dont_items: ["no_fake_prices", "no_fake_discounts", "no_guarantee_results"],
      custom_should_not_do: [],
      extra_restrictions: null,
      good_response_example: null,
      bad_response_example: null,
    },
  },
  {
    id: "faq",
    label: "FAQ / Perguntas Frequentes",
    tagline: "Responde perguntas comuns de forma objetiva",
    description: "Responde rapidamente às perguntas mais comuns, sem se desviar do escopo da empresa.",
    icon: "💬",
    guidedConfig: {
      role: "initial_support",
      main_objective: "Responder as perguntas mais frequentes de forma rápida e objetiva.",
      posture: "direct",
      initiative: "only_respond",
      when_no_info: "direct_to_team",
      do_items: ["answer_company_questions", "use_knowledge_base", "explain_products"],
      custom_should_do: [],
      dont_items: ["no_fake_prices", "no_out_of_scope", "no_guarantee_results"],
      custom_should_not_do: [],
      extra_restrictions: null,
      good_response_example: null,
      bad_response_example: null,
    },
  },
  {
    id: "onboarding",
    label: "Onboarding",
    tagline: "Guia novos clientes na adoção do produto",
    description: "Acompanha novos usuários nos primeiros passos, explica funcionalidades e incentiva o uso.",
    icon: "🚀",
    guidedConfig: {
      role: "relationship_postsale",
      main_objective: "Guiar novos clientes nos primeiros passos e ajudá-los a tirar o máximo do produto.",
      posture: "educational",
      initiative: "respond_suggest",
      when_no_info: "ask_context",
      do_items: ["answer_company_questions", "explain_products", "guide_next_step", "use_knowledge_base"],
      custom_should_do: [],
      dont_items: ["no_fake_prices", "no_out_of_scope"],
      custom_should_not_do: [],
      extra_restrictions: null,
      good_response_example: null,
      bad_response_example: null,
    },
  },
  {
    id: "collections",
    label: "Cobrança e Follow-up",
    tagline: "Acompanha pagamentos com tom profissional",
    description: "Envia lembretes, negocia prazos e conduz conversas de cobrança com profissionalismo.",
    icon: "🔔",
    guidedConfig: {
      role: "custom",
      main_objective: "Acompanhar clientes com pendências, comunicar prazos e orientar sobre regularização.",
      posture: "direct",
      initiative: "respond_suggest",
      when_no_info: "direct_to_team",
      do_items: ["guide_next_step", "answer_company_questions"],
      custom_should_do: ["Comunicar prazos com clareza", "Oferecer opções de regularização quando disponíveis"],
      dont_items: ["no_fake_discounts", "no_guarantee_results", "no_sensitive_data"],
      custom_should_not_do: [],
      extra_restrictions: null,
      good_response_example: null,
      bad_response_example: null,
    },
  },
  {
    id: "internal_assistant",
    label: "Assistente Interno",
    tagline: "Responde dúvidas da equipe sobre processos",
    description: "Ajuda a equipe a encontrar informações internas, processos e políticas da empresa.",
    icon: "🏢",
    guidedConfig: {
      role: "custom",
      main_objective: "Responder dúvidas da equipe interna sobre processos, políticas e informações da empresa.",
      posture: "direct",
      initiative: "only_respond",
      when_no_info: "ask_context",
      do_items: ["answer_company_questions", "use_knowledge_base", "explain_products"],
      custom_should_do: [],
      dont_items: ["no_out_of_scope", "no_guarantee_results"],
      custom_should_not_do: [],
      extra_restrictions: null,
      good_response_example: null,
      bad_response_example: null,
    },
  },
  {
    id: "blank",
    label: "Criar do zero",
    tagline: "Configure tudo manualmente",
    description: "Começa com instruções em branco. Ideal para quem já sabe exatamente o que quer.",
    icon: "✏️",
    guidedConfig: {
      role: null,
      main_objective: null,
      posture: null,
      initiative: null,
      when_no_info: null,
      do_items: [],
      custom_should_do: [],
      dont_items: [],
      custom_should_not_do: [],
      extra_restrictions: null,
      good_response_example: null,
      bad_response_example: null,
    },
  },
];
