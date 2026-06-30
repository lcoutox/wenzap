const screens = [
  {
    label: "Painel operacional",
    caption: "Veja quais agentes estão prontos e o que está acontecendo na operação.",
    rows: [
      { k: "Conversas abertas", v: "24" },
      { k: "Agentes ativos", v: "3" },
      { k: "Canais conectados", v: "5" },
      { k: "Itens disponíveis", v: "142" },
    ],
  },
  {
    label: "Ferramentas do agente",
    caption: "Defina quais informações e ofertas cada agente pode consultar.",
    tools: ["Informações da empresa", "Produtos e serviços", "Conversas organizadas"],
  },
  {
    label: "Conversas centralizadas",
    caption: "Acompanhe respostas da IA e atendimento humano no mesmo lugar.",
    convs: ["Carlos S. · WhatsApp · IA respondendo", "Ana Lima · Site · IA respondendo", "Marcos R. · WhatsApp · Atendimento humano"],
  },
];

export function ProductPreviewSection() {
  return (
    <section className="py-20 bg-nb-bg">
      <div className="max-w-6xl mx-auto px-4">
        <div className="text-center mb-14">
          <h2 className="text-2xl md:text-3xl font-bold text-nb-text">Produto em ação</h2>
          <p className="mt-4 text-nb-secondary text-base max-w-xl mx-auto">
            Uma plataforma pensada para quem quer operar com IA de verdade — não para demos.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-5">
          {screens.map((s) => (
            <div key={s.label} className="rounded-2xl border border-nb-border bg-nb-surface overflow-hidden flex flex-col">
              <div className="bg-nb-panel border-b border-nb-border px-4 py-2.5 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-nb-primary" />
                <span className="text-xs font-medium text-nb-secondary">{s.label}</span>
              </div>
              <div className="p-4 flex flex-col gap-2.5 flex-1">
                {"rows" in s && s.rows?.map((r) => (
                  <div key={r.k} className="flex items-center justify-between py-2 px-3 rounded-lg bg-nb-elevated">
                    <span className="text-xs text-nb-muted">{r.k}</span>
                    <span className="text-sm font-bold text-nb-text">{r.v}</span>
                  </div>
                ))}
                {"tools" in s && s.tools?.map((t) => (
                  <div key={t} className="flex items-center gap-2.5 py-2 px-3 rounded-lg bg-nb-elevated">
                    <span className="w-1.5 h-1.5 rounded-full bg-nb-success" />
                    <span className="text-xs text-nb-secondary">{t}</span>
                    <span className="ml-auto text-[10px] font-medium text-nb-primary bg-nb-primary-bg px-1.5 py-0.5 rounded-full">Ativo</span>
                  </div>
                ))}
                {"convs" in s && s.convs?.map((c) => (
                  <div key={c} className="py-2 px-3 rounded-lg bg-nb-elevated">
                    <span className="text-xs text-nb-secondary">{c}</span>
                  </div>
                ))}
              </div>
              <p className="px-4 pb-4 text-[11px] text-nb-muted leading-relaxed">{s.caption}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
