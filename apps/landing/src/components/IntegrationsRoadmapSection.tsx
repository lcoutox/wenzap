const available = [
  { label: "Atender pelo WhatsApp", tag: "WhatsApp Business Platform" },
  { label: "Colocar um agente no site", tag: "Web Widget" },
  { label: "Ensinar a IA com informações da empresa", tag: "Base de Conhecimento" },
  { label: "Apresentar produtos e serviços", tag: "Catálogo" },
  { label: "Centralizar todas as conversas", tag: "Inbox" },
];

const coming = [
  { label: "Consultar dados de gestão", tag: "Bling" },
  { label: "Vender e acompanhar marketplaces", tag: "Mercado Livre" },
  { label: "Atender em novos canais", tag: "Telegram e Slack" },
  { label: "Executar ações em sistemas externos", tag: "HTTP Tools" },
  { label: "Retomar oportunidades paradas", tag: "Follow-up automático" },
];

export function IntegrationsRoadmapSection() {
  return (
    <section className="py-20 bg-nb-surface">
      <div className="max-w-5xl mx-auto px-4">
        <div className="text-center mb-14">
          <h2 className="text-2xl md:text-3xl font-bold text-nb-text">
            Conecte sua operação aos poucos
          </h2>
          <p className="mt-4 text-nb-secondary text-base max-w-xl mx-auto">
            Comece com atendimento e conversas. Depois, conecte sistemas, canais e fontes de dados
            conforme sua empresa cresce.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="rounded-2xl border border-nb-border bg-nb-panel p-6">
            <p className="text-xs font-semibold text-nb-primary uppercase tracking-wider mb-4">Disponível hoje</p>
            <ul className="flex flex-col gap-4">
              {available.map((item) => (
                <li key={item.tag} className="flex items-start gap-3">
                  <span className="w-1.5 h-1.5 rounded-full bg-nb-success flex-shrink-0 mt-1.5" />
                  <div>
                    <p className="text-sm text-nb-text">{item.label}</p>
                    <p className="text-[11px] text-nb-muted mt-0.5">{item.tag}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-nb-border bg-nb-panel p-6">
            <p className="text-xs font-semibold text-nb-muted uppercase tracking-wider mb-4">Em breve</p>
            <ul className="flex flex-col gap-4">
              {coming.map((item) => (
                <li key={item.tag} className="flex items-start gap-3">
                  <span className="w-1.5 h-1.5 rounded-full bg-nb-border-strong flex-shrink-0 mt-1.5" />
                  <div>
                    <p className="text-sm text-nb-secondary">{item.label}</p>
                    <p className="text-[11px] text-nb-muted mt-0.5">{item.tag}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-nb-muted">
          Integrações em roadmap podem variar conforme disponibilidade e aprovação das plataformas.
        </p>
      </div>
    </section>
  );
}
