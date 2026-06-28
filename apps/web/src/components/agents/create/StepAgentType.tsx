import {
  HeadphonesIcon,
  TrendingUp,
  Wrench,
  CalendarDays,
  Bell,
  SlidersHorizontal,
} from "lucide-react";
import type { AgentTypeId } from "./wizard-types";

const TYPES: {
  id: AgentTypeId;
  label: string;
  description: string;
  icon: React.ReactNode;
}[] = [
  {
    id: "support",
    label: "Atendimento ao cliente",
    description: "Responde dúvidas frequentes, orienta clientes e usa o conhecimento da empresa.",
    icon: <HeadphonesIcon className="w-5 h-5" />,
  },
  {
    id: "sales",
    label: "Vendas / qualificação de leads",
    description: "Entende o interesse do cliente, faz perguntas de qualificação e direciona oportunidades.",
    icon: <TrendingUp className="w-5 h-5" />,
  },
  {
    id: "tech",
    label: "Suporte técnico",
    description: "Ajuda usuários a resolver problemas, seguir procedimentos e encontrar respostas.",
    icon: <Wrench className="w-5 h-5" />,
  },
  {
    id: "scheduling",
    label: "Agendamento",
    description: "Ajuda clientes a consultar horários, tirar dúvidas e avançar para um agendamento.",
    icon: <CalendarDays className="w-5 h-5" />,
  },
  {
    id: "collections",
    label: "Cobrança / follow-up",
    description: "Envia lembretes e conduz conversas de acompanhamento com tom profissional.",
    icon: <Bell className="w-5 h-5" />,
  },
  {
    id: "blank",
    label: "Criar do zero",
    description: "Comece com uma configuração neutra e personalize manualmente.",
    icon: <SlidersHorizontal className="w-5 h-5" />,
  },
];

export function StepAgentType({
  value,
  onChange,
}: {
  value: AgentTypeId | null;
  onChange: (v: AgentTypeId) => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-nb-text">
          Que tipo de agente você quer criar?
        </h2>
        <p className="text-sm text-nb-muted mt-1">
          Escolha um ponto de partida. Você poderá ajustar tudo antes de finalizar.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {TYPES.map((t) => {
          const selected = value === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => onChange(t.id)}
              className={`text-left flex items-start gap-3 p-4 rounded-xl border transition-all ${
                selected
                  ? "border-nb-primary bg-nb-primary-bg ring-1 ring-nb-primary/30"
                  : "border-nb-border bg-nb-elevated hover:border-nb-border-strong hover:bg-nb-panel"
              }`}
            >
              <div
                className={`mt-0.5 flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center transition-colors ${
                  selected
                    ? "bg-nb-primary text-white"
                    : "bg-nb-panel text-nb-muted border border-nb-border"
                }`}
              >
                {t.icon}
              </div>
              <div className="min-w-0">
                <p
                  className={`text-sm font-semibold leading-snug ${
                    selected ? "text-nb-primary-strong" : "text-nb-text"
                  }`}
                >
                  {t.label}
                </p>
                <p className="text-xs text-nb-muted mt-0.5 leading-relaxed">
                  {t.description}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
