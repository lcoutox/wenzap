import { BookOpen, Globe, Hand, CheckCircle2, Clock } from "lucide-react";

type ToolCard = {
  icon: React.ElementType;
  name: string;
  description: string;
  phase: string;
};

const TOOLS: ToolCard[] = [
  {
    icon: BookOpen,
    name: "Base de Conhecimento",
    description: "Conecte documentos, URLs e dados estruturados para que o agente responda com base no seu conteúdo.",
    phase: "Phase 4",
  },
  {
    icon: Globe,
    name: "HTTP Request",
    description: "Execute chamadas a APIs externas durante a conversa para buscar dados em tempo real.",
    phase: "Phase 6",
  },
  {
    icon: Hand,
    name: "Solicitar Humano",
    description: "Transfira a conversa para um atendente humano quando necessário.",
    phase: "Phase 5",
  },
  {
    icon: CheckCircle2,
    name: "Marcar como Resolvido",
    description: "Encerre automaticamente uma conversa após a resolução do problema.",
    phase: "Phase 5",
  },
  {
    icon: Clock,
    name: "Follow-up",
    description: "Agende mensagens de acompanhamento automáticas após um período de inatividade.",
    phase: "Phase 6",
  },
];

export function ConfigFerramentas() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-gray-900">Ferramentas do agente</h2>
        <p className="text-sm text-gray-500 mt-1">
          Ferramentas ampliam as capacidades do agente. Serão liberadas progressivamente nas próximas fases.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {TOOLS.map(({ icon: Icon, name, description, phase }) => (
          <div
            key={name}
            className="bg-white rounded-xl border border-gray-200 p-5 opacity-70"
          >
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-lg bg-gray-50 border border-gray-200 flex items-center justify-center flex-shrink-0">
                <Icon className="w-4 h-4 text-gray-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-sm font-semibold text-gray-700">{name}</h3>
                  <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded bg-gray-100 text-gray-400 border border-gray-200 leading-none">
                    {phase}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-1 leading-relaxed">{description}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
