const steps = [
  {
    n: "1",
    title: "Crie um agente para uma função",
    desc: "Defina o objetivo: atendimento, vendas, suporte, agendamento. Cada agente tem um papel claro dentro da sua operação.",
  },
  {
    n: "2",
    title: "Ensine o agente com suas informações",
    desc: "Adicione documentos, perguntas frequentes, políticas e detalhes da empresa. O agente aprende o que você quer que ele saiba.",
  },
  {
    n: "3",
    title: "Cadastre o que sua empresa oferece",
    desc: "Inclua produtos, serviços, planos ou ofertas que o agente pode apresentar e recomendar durante uma conversa.",
  },
  {
    n: "4",
    title: "Conecte seus canais de atendimento",
    desc: "Comece pelo WhatsApp ou pelo widget do seu site. Seus clientes chegam pelo canal deles — o agente responde no mesmo lugar.",
  },
  {
    n: "5",
    title: "Acompanhe e assuma quando quiser",
    desc: "Veja todas as conversas em um painel, monitore o que a IA está fazendo e entre na conversa com um clique quando necessário.",
  },
];

export function HowItWorksSection() {
  return (
    <section id="como-funciona" className="py-20 bg-nb-surface scroll-mt-14">
      <div className="max-w-4xl mx-auto px-4">
        <div className="text-center mb-14">
          <h2 className="text-2xl md:text-3xl font-bold text-nb-text">Como funciona</h2>
          <p className="mt-4 text-nb-secondary text-base">
            Do primeiro agente à operação funcionando em cinco passos simples.
          </p>
        </div>

        <div className="flex flex-col gap-0">
          {steps.map((s, i) => (
            <div key={s.n} className="flex gap-5 relative">
              {i < steps.length - 1 && (
                <div className="absolute left-5 top-10 bottom-0 w-px bg-nb-border" aria-hidden />
              )}
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-nb-primary-bg border border-nb-primary/30 flex items-center justify-center z-10">
                <span className="text-sm font-bold text-nb-primary">{s.n}</span>
              </div>
              <div className="pb-10">
                <h3 className="text-sm font-semibold text-nb-text">{s.title}</h3>
                <p className="mt-1 text-sm text-nb-muted leading-relaxed">{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
