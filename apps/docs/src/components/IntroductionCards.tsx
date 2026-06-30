import {
  Bot,
  Code2,
  DatabaseZap,
  MessagesSquare,
  PanelsTopLeft,
  PlugZap,
} from "lucide-react";

const cards = [
  {
    title: "Plataforma",
    description: "Visão geral da plataforma de operações com agentes.",
    icon: PanelsTopLeft,
  },
  {
    title: "Agentes",
    description: "Crie agentes conectados ao contexto do seu negócio.",
    icon: Bot,
  },
  {
    title: "Base de conhecimento",
    description: "Organize documentos, URLs e informações reutilizáveis.",
    icon: DatabaseZap,
  },
  {
    title: "Canais",
    description: "Publique agentes em canais como WhatsApp, site e API.",
    icon: MessagesSquare,
  },
  {
    title: "Integrações",
    description: "Conecte ferramentas para acionar fluxos e processos.",
    icon: PlugZap,
  },
  {
    title: "API e Webhooks",
    description: "Integre o Wenzap aos sistemas da sua operação.",
    icon: Code2,
  },
];

export function IntroductionCards() {
  return (
    <div className="mt-7 grid gap-4 sm:grid-cols-2">
      {cards.map((card) => {
        const Icon = card.icon;

        return (
          <div
            key={card.title}
            className="group rounded-xl border border-nb-border bg-nb-bg/60 p-5 transition-colors hover:border-nb-primary/50 hover:bg-nb-surface"
          >
            <Icon
              aria-hidden="true"
              className="mb-7 size-7 text-nb-primary transition-transform group-hover:-translate-y-0.5"
              strokeWidth={1.8}
            />
            <h3 className="m-0 text-base font-semibold tracking-normal text-nb-text">
              {card.title}
            </h3>
            <p className="mt-2 text-sm leading-6 text-nb-secondary">
              {card.description}
            </p>
          </div>
        );
      })}
    </div>
  );
}
