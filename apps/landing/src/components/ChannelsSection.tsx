export function ChannelsSection() {
  return (
    <section className="py-20 bg-nb-bg">
      <div className="max-w-5xl mx-auto px-4">
        <div className="grid md:grid-cols-2 gap-10 items-center">
          <div>
            <h2 className="text-2xl md:text-3xl font-bold text-nb-text leading-tight">
              Comece pelo canal que{" "}
              <span className="text-nb-primary">seus clientes já usam.</span>
            </h2>
            <p className="mt-4 text-nb-secondary leading-relaxed text-base">
              Conecte seu WhatsApp pela plataforma oficial da Meta e coloque um agente para atender
              com histórico, IA e controle humano. Adicione o widget no seu site para captar e
              responder visitantes no mesmo momento.
            </p>
            <ul className="mt-6 flex flex-col gap-3">
              {[
                "Atenda pelo WhatsApp que seus clientes já usam todos os dias",
                "Coloque um agente no seu site para responder visitantes",
                "O mesmo agente funciona em múltiplos canais",
                "Todas as conversas centralizadas em um único painel",
              ].map((item) => (
                <li key={item} className="flex items-start gap-3 text-sm text-nb-secondary">
                  <span className="w-5 h-5 flex-shrink-0 rounded-full bg-nb-primary-bg border border-nb-primary/30 flex items-center justify-center mt-0.5">
                    <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                      <path d="M1 3l2 2 4-4" stroke="#00E09A" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="flex flex-col gap-4">
            <div className="rounded-2xl border border-nb-border bg-nb-surface p-5 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-[#25D366]/10 border border-[#25D366]/20 flex-shrink-0">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="#25D366">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z" />
                  <path d="M12 0C5.373 0 0 5.373 0 12c0 2.136.562 4.14 1.541 5.874L0 24l6.299-1.524A11.952 11.952 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.818 9.818 0 01-5.002-1.374l-.358-.213-3.742.906.95-3.633-.232-.373A9.818 9.818 0 1112 21.818z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-nb-text">Atenda pelo WhatsApp que seus clientes já usam</p>
                <p className="text-xs text-nb-muted mt-0.5">Integração com WhatsApp Business Platform</p>
              </div>
              <span className="ml-auto text-xs font-medium text-nb-success bg-nb-success/10 px-2 py-1 rounded-full flex-shrink-0">Disponível</span>
            </div>

            <div className="rounded-2xl border border-nb-border bg-nb-surface p-5 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-nb-primary-bg border border-nb-primary/20 flex-shrink-0">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00E09A" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-nb-text">Coloque um agente no seu site</p>
                <p className="text-xs text-nb-muted mt-0.5">Web Widget — uma linha de código</p>
              </div>
              <span className="ml-auto text-xs font-medium text-nb-success bg-nb-success/10 px-2 py-1 rounded-full flex-shrink-0">Disponível</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
