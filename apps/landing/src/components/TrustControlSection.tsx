const points = [
  "Você define o que cada agente pode consultar — nenhum agente acessa mais do que você autorizar.",
  "Você escolhe quais informações da empresa ficam disponíveis para cada agente.",
  "Você limita quais produtos ou serviços cada agente pode apresentar.",
  "Sua equipe pode assumir conversas quando precisar, sem perder o histórico.",
  "Tudo fica registrado — você pode auditar o que foi dito e quando.",
];

export function TrustControlSection() {
  return (
    <section className="py-20 bg-nb-bg">
      <div className="max-w-5xl mx-auto px-4">
        <div className="grid md:grid-cols-2 gap-12 items-center">
          <div>
            <h2 className="text-2xl md:text-3xl font-bold text-nb-text leading-tight">
              Você vê tudo. E{" "}
              <span className="text-nb-primary">assume quando quiser.</span>
            </h2>
            <p className="mt-4 text-nb-secondary leading-relaxed text-base">
              É a parte &ldquo;à vista&rdquo; da promessa. Você decide o que cada agente pode fazer,
              vê cada passo que ele deu, e sua equipe assume qualquer conversa quando quiser. Nada de
              caixa-preta com o seu cliente.
            </p>
          </div>

          <ul className="flex flex-col gap-4">
            {points.map((p) => (
              <li key={p} className="flex items-start gap-3">
                <span className="w-5 h-5 flex-shrink-0 rounded-full bg-nb-primary-bg border border-nb-primary/30 flex items-center justify-center mt-0.5">
                  <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                    <path d="M1 3l2 2 4-4" stroke="#00E09A" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
                <span className="text-sm text-nb-secondary leading-relaxed">{p}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
