"use client";

import { getAppSignupUrl } from "@/lib/signup";
import { trackLandingEvent } from "@/lib/tracking";

export function FinalCTASection() {
  return (
    <section className="py-24 bg-nb-surface">
      <div className="max-w-3xl mx-auto px-4 text-center">
        <h2 className="text-3xl md:text-4xl font-bold text-nb-text leading-tight">
          Transforme IA em operação.
        </h2>
        <p className="mt-5 text-nb-secondary text-base md:text-lg max-w-xl mx-auto leading-relaxed">
          Comece com agentes de IA trabalhando no atendimento, vendas e relacionamento da sua
          empresa — com ferramentas, canais e controle humano.
        </p>
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            trackLandingEvent("final_cta_click");
            window.location.href = getAppSignupUrl();
          }}
          className="mt-10 inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-nb-primary text-nb-bg font-bold text-base hover:bg-nb-primary-strong transition-colors"
        >
          Quero testar o Wenzap
        </a>
        <p className="mt-4 text-xs text-nb-muted">Sem cartão de crédito para começar.</p>
      </div>
    </section>
  );
}
