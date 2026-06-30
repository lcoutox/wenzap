import { BookOpen, Package, MessageSquare, Radio, UserCheck } from "lucide-react";

const tools = [
  {
    icon: BookOpen,
    benefit: "Ensine a IA sobre sua empresa",
    description:
      "Adicione documentos, FAQs, políticas e informações importantes. O agente consulta esse conteúdo antes de responder qualquer cliente.",
    tag: "Base de Conhecimento",
  },
  {
    icon: Package,
    benefit: "Mostre o que sua empresa oferece",
    description:
      "Cadastre produtos, serviços, planos ou ofertas para que o agente possa apresentar opções e recomendar o que faz sentido durante a conversa.",
    tag: "Catálogo",
  },
  {
    icon: MessageSquare,
    benefit: "Organize conversas em um só lugar",
    description:
      "Acompanhe histórico, respostas da IA e atendimento humano sem depender de conversas espalhadas no celular ou em planilhas.",
    tag: "Inbox",
  },
  {
    icon: Radio,
    benefit: "Atenda nos canais que seus clientes usam",
    description:
      "Comece pelo WhatsApp e pelo widget no seu site. O mesmo agente funciona nos dois canais, com histórico unificado.",
    tag: "Canais",
  },
  {
    icon: UserCheck,
    benefit: "Mantenha humanos no controle",
    description:
      "A IA cuida do repetitivo, mas sua equipe pode assumir qualquer conversa quando quiser — e recebe todo o contexto do que já foi dito.",
    tag: "Controle humano",
  },
];

export function AgentToolsSection() {
  return (
    <section className="py-20 bg-nb-bg">
      <div className="max-w-6xl mx-auto px-4">
        <div className="text-center mb-14">
          <h2 className="text-2xl md:text-3xl font-bold text-nb-text">
            Agentes que entendem sua empresa e atendem seus clientes.
          </h2>
          <p className="mt-4 text-nb-secondary max-w-xl mx-auto text-base">
            Cada agente do Wenzap pode ser conectado às informações, produtos e canais da sua
            empresa — não é só um bot genérico.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {tools.map(({ icon: Icon, benefit, description, tag }) => (
            <div
              key={tag}
              className="rounded-2xl border border-nb-border bg-nb-surface p-6 flex flex-col gap-3 hover:border-nb-primary/30 transition-colors"
            >
              <div className="w-10 h-10 rounded-xl bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center">
                <Icon className="w-5 h-5 text-nb-primary" />
              </div>
              <h3 className="text-sm font-semibold text-nb-text">{benefit}</h3>
              <p className="text-sm text-nb-muted leading-relaxed flex-1">{description}</p>
              <span className="text-[11px] font-medium text-nb-primary/70 bg-nb-primary-bg/50 px-2 py-0.5 rounded-full self-start">
                {tag}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
