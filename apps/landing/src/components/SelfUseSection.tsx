"use client";

import { trackLandingEvent } from "@/lib/tracking";
import { openWenzapWidget } from "@/lib/widget";

export function SelfUseSection() {
  return (
    <section className="py-20 bg-nb-surface">
      <div className="max-w-4xl mx-auto px-4">
        <div className="rounded-2xl border border-nb-primary/20 bg-nb-primary-bg/10 p-8 md:p-10 text-center">
          <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-nb-primary-bg text-nb-primary border border-nb-primary/20 mb-5">
            <span className="w-1.5 h-1.5 rounded-full bg-nb-primary animate-pulse" />
            Este site também é operado pelo Wenzap
          </span>

          <h2 className="text-xl md:text-2xl font-bold text-nb-text">
            O agente no canto da tela foi criado no próprio Wenzap.
          </h2>

          <p className="mt-4 text-nb-secondary leading-relaxed max-w-xl mx-auto text-base">
            Ele foi treinado com informações sobre o produto e pode responder dúvidas, explicar
            recursos e encaminhar a conversa para um humano quando necessário. Essa é a mesma
            experiência que sua empresa pode oferecer aos seus clientes.
          </p>

          <button
            onClick={() => {
              trackLandingEvent("widget_cta_click");
              openWenzapWidget();
            }}
            className="mt-7 inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-nb-primary text-nb-bg font-semibold text-sm hover:bg-nb-primary-strong transition-colors"
          >
            Conversar com o agente
          </button>
        </div>
      </div>
    </section>
  );
}
