const before = [
  "Respostas soltas, sem contexto da empresa",
  "Depende de copiar e colar manualmente",
  "Sem histórico das conversas",
  "Sem processo definido para sua equipe",
];

const after = [
  "Agentes com função clara e informações conectadas",
  "Respostas automáticas com contexto real da empresa",
  "Histórico centralizado em um só lugar",
  "Humano no controle, entra quando precisar",
];

export function MindsetSection() {
  return (
    <section className="py-20 bg-nb-surface">
      <div className="max-w-5xl mx-auto px-4">
        <div className="text-center mb-14">
          <h2 className="text-2xl md:text-3xl font-bold text-nb-text">
            IA não deveria ser só uma conversa solta.
          </h2>
          <p className="mt-4 text-nb-secondary max-w-2xl mx-auto text-base leading-relaxed">
            Muitas empresas usam IA como um chat: alguém pergunta, copia uma resposta e tenta
            encaixar no trabalho. O Wenzap leva a IA para dentro da operação, onde agentes podem
            atender clientes, consultar informações e ajudar sua equipe a trabalhar melhor.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="rounded-2xl border border-nb-border bg-nb-panel p-6">
            <p className="text-xs font-semibold text-nb-muted uppercase tracking-wider mb-4">
              IA usada como chat
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
              IA trabalhando na operação
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
