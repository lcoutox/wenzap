"use client";

import { openWenzapWidget } from "@/lib/widget";
import { trackLandingEvent } from "@/lib/tracking";

export function FinalCTASection() {
  return (
    <section className="py-24 bg-nb-surface">
      <div className="max-w-3xl mx-auto px-4 text-center">
        <h2 className="text-3xl md:text-4xl font-bold text-nb-text leading-tight">
          Pare de perder venda que já estava na mão.
        </h2>
        <p className="mt-5 text-nb-secondary text-base md:text-lg max-w-xl mx-auto leading-relaxed">
          Estamos abrindo o Wenzap pra um grupo pequeno de negócios agora. Você fala direto com quem
          construiu o produto, sem intermediário.
        </p>
        <button
          onClick={() => {
            trackLandingEvent("final_cta_click");
            openWenzapWidget();
          }}
          className="mt-10 inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-nb-primary text-nb-bg font-bold text-base hover:bg-nb-primary-strong transition-colors"
        >
          Entrar no beta fechado
        </button>
        <p className="mt-4 text-xs text-nb-muted">Beta fechado, por convite. Vagas limitadas.</p>
      </div>
    </section>
  );
}
