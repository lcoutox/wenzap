const before = [
  "Responde e para por aí",
  "Deixa o lead esfriar, sem follow-up",
  "Não qualifica nem agenda nada",
  "Você não vê o que ele fez",
];

const after = [
  "Qualifica quem tem verba e interesse real",
  "Agenda a visita antes do lead esfriar",
  "Cobra o retorno que não veio",
  "Mostra cada passo pra você assumir quando quiser",
];

export function MindsetSection() {
  return (
    <section className="py-20 bg-nb-surface">
      <div className="max-w-5xl mx-auto px-4">
        <div className="text-center mb-14">
          <h2 className="text-2xl md:text-3xl font-bold text-nb-text">
            Um chatbot que só responde não vende nada.
          </h2>
          <p className="mt-4 text-nb-secondary max-w-2xl mx-auto text-base leading-relaxed">
            Responder rápido é o mínimo. O que fecha a venda é o que acontece depois do &ldquo;olá&rdquo;:
            qualificar quem tem verba, agendar a visita antes do lead esfriar e cobrar o retorno que
            não veio. O Wenzap faz isso sozinho, e mostra cada passo pra você assumir quando quiser.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="rounded-2xl border border-nb-border bg-nb-panel p-6">
            <p className="text-xs font-semibold text-nb-muted uppercase tracking-wider mb-4">
              Chatbot que só responde
            </p>
            <ul className="flex flex-col gap-3">
              {before.map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <span className="w-4 h-4 flex-shrink-0 rounded-full border border-nb-border-strong mt-0.5 flex items-center justify-center">
                    <span className="w-1.5 h-0.5 bg-nb-muted rounded-full" />
                  </span>
                  <span className="text-sm text-nb-muted">{item}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-nb-primary/20 bg-nb-primary-bg/20 p-6">
            <p className="text-xs font-semibold text-nb-primary uppercase tracking-wider mb-4">
              Agente que opera
            </p>
            <ul className="flex flex-col gap-3">
              {after.map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <span className="w-4 h-4 flex-shrink-0 rounded-full bg-nb-primary-bg border border-nb-primary/40 mt-0.5 flex items-center justify-center">
                    <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                      <path d="M1 3l2 2 4-4" stroke="#00E09A" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                  <span className="text-sm text-nb-text">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
