import { Send, Download, Zap } from "lucide-react";

const ITEMS = [
  {
    icon: Send,
    name: "Webhook de saída",
    description: "Notifique sistemas externos quando eventos ocorrerem neste agente (nova conversa, mensagem recebida, lead qualificado).",
    phase: "Phase 6",
  },
  {
    icon: Download,
    name: "Buscar dados externos",
    description: "Execute chamadas a APIs externas durante a conversa para enriquecer as respostas com dados em tempo real.",
    phase: "Phase 6",
  },
  {
    icon: Zap,
    name: "Eventos do agente",
    description: "Assine eventos específicos do agente para acionar automações em ferramentas como Zapier, Make ou n8n.",
    phase: "Phase 6",
  },
];

export function ConfigWebhooks() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-gray-900">Webhooks e eventos</h2>
        <p className="text-sm text-gray-500 mt-1">
          Conecte este agente a sistemas externos através de webhooks e eventos. Disponível na Phase 6.
        </p>
      </div>

      <div className="space-y-4">
        {ITEMS.map(({ icon: Icon, name, description, phase }) => (
          <div
            key={name}
            className="bg-white rounded-xl border border-gray-200 p-5 opacity-70 flex items-start gap-4"
          >
            <div className="w-10 h-10 rounded-lg bg-gray-50 border border-gray-200 flex items-center justify-center flex-shrink-0">
              <Icon className="w-5 h-5 text-gray-400" />
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
            <button
              type="button"
              disabled
              className="flex-shrink-0 px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-100 text-gray-400 border border-gray-200 cursor-not-allowed"
            >
              Configurar
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
