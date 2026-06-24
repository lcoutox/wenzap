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
    tagColor: "bg-nb-primary-bg text-nb-primary-strong border-nb-primary/20",
  },
  {
    icon: MessageCircle,
    name: "WhatsApp",
    description: "Integre o agente diretamente com a API oficial do WhatsApp Business.",
    tag: "Phase 6",
    tagColor: "bg-nb-success/10 text-nb-success border-nb-success/20",
  },
  {
    icon: Hash,
    name: "Instagram",
    description: "Responda mensagens diretas e comentários pelo Instagram.",
    tag: "Phase 6",
    tagColor: "bg-nb-danger/10 text-nb-danger border-nb-danger/20",
  },
  {
    icon: Send,
    name: "Telegram",
    description: "Conecte o agente a um bot no Telegram.",
    tag: "Phase 6",
    tagColor: "bg-nb-info/10 text-nb-info border-nb-info/20",
  },
  {
    icon: Layers,
    name: "Slack",
    description: "Atenda equipes internas diretamente no Slack.",
    tag: "Phase 6",
    tagColor: "bg-nb-elevated text-nb-muted border-nb-border",
  },
  {
    icon: Code2,
    name: "API",
    description: "Acesse o agente via API REST para integrações personalizadas.",
    tag: "Phase 5",
    tagColor: "bg-nb-elevated text-nb-secondary border-nb-border",
  },
];

export function ImplantarPlaceholder() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-nb-text">Canais de implantação</h2>
        <p className="text-sm text-nb-muted mt-1">
          Escolha onde este agente vai operar. Os canais serão ativados progressivamente nas próximas fases.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {CHANNELS.map(({ icon: Icon, name, description, tag, tagColor }) => (
          <div
            key={name}
            className="bg-nb-panel rounded-2xl border border-nb-border p-5 flex flex-col gap-3 opacity-80 hover:opacity-100 transition-opacity"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="w-10 h-10 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
                <Icon className="w-5 h-5 text-nb-muted" />
              </div>
              <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${tagColor}`}>
                {tag}
              </span>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-nb-secondary">{name}</h3>
              <p className="text-xs text-nb-muted mt-1 leading-relaxed">{description}</p>
            </div>
            <button
              type="button"
              disabled
              className="mt-auto w-full py-1.5 text-xs font-medium rounded-xl bg-nb-elevated text-nb-muted cursor-not-allowed border border-nb-border"
            >
              Em breve
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
