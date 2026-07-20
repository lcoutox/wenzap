"use client";

import { openWenzapWidget } from "@/lib/widget";
import { trackLandingEvent } from "@/lib/tracking";

export function LandingHero() {
  return (
    <section className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 50% at 50% -10%, rgba(0,224,154,0.12) 0%, transparent 70%)",
        }}
      />

      <div className="relative max-w-6xl mx-auto px-4 pt-20 pb-16 md:pt-28 md:pb-24 text-center">
        <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-nb-primary-bg text-nb-primary border border-nb-primary/20 mb-6">
          <span className="w-1.5 h-1.5 rounded-full bg-nb-primary animate-pulse" />
          IA que opera, não só conversa
        </span>

        <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold text-nb-text leading-tight tracking-tight max-w-4xl mx-auto">
          Responder rápido não vende.{" "}
          <span className="text-nb-primary">Vender é o que vem depois.</span>
        </h1>

        <p className="mt-6 text-base md:text-lg text-nb-secondary max-w-2xl mx-auto leading-relaxed">
          O Wenzap qualifica o lead, agenda a visita e faz o follow-up sozinho, no WhatsApp e no seu
          site. Você vê cada passo e assume quando quiser.
        </p>

        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
          <button
            onClick={() => {
              trackLandingEvent("hero_cta_click", { variant: "primary" });
              openWenzapWidget();
            }}
            className="w-full sm:w-auto px-6 py-3 rounded-xl bg-nb-primary text-nb-bg font-semibold text-sm hover:bg-nb-primary-strong transition-colors"
          >
            Entrar no beta fechado
          </button>
          <a
            href="#como-funciona"
            onClick={() => trackLandingEvent("hero_cta_click", { variant: "secondary" })}
            className="w-full sm:w-auto px-6 py-3 rounded-xl border border-nb-border text-nb-secondary font-medium text-sm hover:bg-nb-elevated hover:text-nb-text transition-colors"
          >
            Ver como funciona
          </a>
        </div>

        {/* Product screenshot */}
        <div className="mt-16 max-w-5xl mx-auto">
          <div className="rounded-2xl border border-nb-border overflow-hidden shadow-2xl">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/screenshots/inbox.png"
              alt="Inbox do Wenzap: o agente qualifica o lead, agenda a visita e a conversa é marcada como resolvida"
              width={1920}
              height={1032}
              className="w-full h-auto"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
