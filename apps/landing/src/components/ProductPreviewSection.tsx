const shots = [
  {
    src: "/screenshots/dashboard.png",
    label: "Painel operacional",
    caption: "Agentes, canais, conversas e catálogo num lugar só.",
  },
  {
    src: "/screenshots/pipeline.png",
    label: "Funil de vendas",
    caption: "Cada lead vira um card e anda até a visita agendada e o fechamento.",
  },
  {
    src: "/screenshots/auditoria.png",
    label: "Auditoria",
    caption:
      "Todo turno que o agente rodou: o que respondeu e o que executou, com sucesso ou falha.",
  },
];

export function ProductPreviewSection() {
  return (
    <section className="py-20 bg-nb-bg">
      <div className="max-w-5xl mx-auto px-4">
        <div className="text-center mb-14">
          <h2 className="text-2xl md:text-3xl font-bold text-nb-text">Produto em ação</h2>
          <p className="mt-4 text-nb-secondary text-base max-w-xl mx-auto">
            Uma plataforma pensada pra quem quer operar com IA de verdade, não pra fazer demo.
          </p>
        </div>

        <div className="flex flex-col gap-12">
          {shots.map((s) => (
            <div key={s.src} className="flex flex-col gap-3">
              <div className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-3">
                <h3 className="text-sm font-semibold text-nb-text">{s.label}</h3>
                <p className="text-sm text-nb-muted">{s.caption}</p>
              </div>
              <div className="rounded-2xl border border-nb-border overflow-hidden shadow-2xl">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={s.src}
                  alt={`${s.label} — ${s.caption}`}
                  width={1920}
                  height={1032}
                  className="w-full h-auto"
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
