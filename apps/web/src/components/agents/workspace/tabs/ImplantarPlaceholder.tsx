import { Globe, MessageCircle, Hash, Send, Layers, Code2 } from "lucide-react";

type ChannelCard = {
  icon: React.ElementType;
  name: string;
  description: string;
  tag: string;
  tagColor: string;
};

const CHANNELS: ChannelCard[] = [
  {
    icon: Globe,
    name: "Website",
    description: "Widget de chat incorporado em qualquer site ou aplicação web.",
    tag: "Phase 5",
    tagColor: "bg-indigo-50 text-indigo-600 border-indigo-200",
  },
  {
    icon: MessageCircle,
    name: "WhatsApp",
    description: "Integre o agente diretamente com a API oficial do WhatsApp Business.",
    tag: "Phase 6",
    tagColor: "bg-green-50 text-green-700 border-green-200",
  },
  {
    icon: Hash,
    name: "Instagram",
    description: "Responda mensagens diretas e comentários pelo Instagram.",
    tag: "Phase 6",
    tagColor: "bg-pink-50 text-pink-600 border-pink-200",
  },
  {
    icon: Send,
    name: "Telegram",
    description: "Conecte o agente a um bot no Telegram.",
    tag: "Phase 6",
    tagColor: "bg-sky-50 text-sky-600 border-sky-200",
  },
  {
    icon: Layers,
    name: "Slack",
    description: "Atenda equipes internas diretamente no Slack.",
    tag: "Phase 6",
    tagColor: "bg-purple-50 text-purple-600 border-purple-200",
  },
  {
    icon: Code2,
    name: "API",
    description: "Acesse o agente via API REST para integrações personalizadas.",
    tag: "Phase 5",
    tagColor: "bg-gray-100 text-gray-600 border-gray-200",
  },
];

export function ImplantarPlaceholder() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-gray-900">Canais de implantação</h2>
        <p className="text-sm text-gray-500 mt-1">
          Escolha onde este agente vai operar. Os canais serão ativados progressivamente nas próximas fases.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {CHANNELS.map(({ icon: Icon, name, description, tag, tagColor }) => (
          <div
            key={name}
            className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-3 opacity-80 hover:opacity-100 transition-opacity"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="w-10 h-10 rounded-lg bg-gray-50 border border-gray-200 flex items-center justify-center flex-shrink-0">
                <Icon className="w-5 h-5 text-gray-500" />
              </div>
              <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${tagColor}`}>
                {tag}
              </span>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-800">{name}</h3>
              <p className="text-xs text-gray-500 mt-1 leading-relaxed">{description}</p>
            </div>
            <button
              type="button"
              disabled
              className="mt-auto w-full py-1.5 text-xs font-medium rounded-lg bg-gray-100 text-gray-400 cursor-not-allowed border border-gray-200"
            >
              Em breve
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
