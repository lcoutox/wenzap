"use client";

import { getAppSignupUrl } from "@/lib/signup";
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
          Agentes de IA para operação de empresas
        </span>

        <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold text-nb-text leading-tight tracking-tight max-w-4xl mx-auto">
          Coloque agentes de IA para trabalhar{" "}
          <span className="text-nb-primary">na sua operação</span>
        </h1>

        <p className="mt-6 text-base md:text-lg text-nb-secondary max-w-2xl mx-auto leading-relaxed">
          O Wenzap ajuda empresas a atender clientes, organizar conversas e automatizar partes do
          atendimento e vendas com agentes de IA — sem tirar sua equipe do controle.
        </p>

        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              trackLandingEvent("hero_cta_click", { variant: "primary" });
              window.location.href = getAppSignupUrl();
            }}
            className="w-full sm:w-auto px-6 py-3 rounded-xl bg-nb-primary text-nb-bg font-semibold text-sm hover:bg-nb-primary-strong transition-colors"
          >
            Quero testar o Wenzap
          </a>
          <a
            href="#como-funciona"
            onClick={() => trackLandingEvent("hero_cta_click", { variant: "secondary" })}
            className="w-full sm:w-auto px-6 py-3 rounded-xl border border-nb-border text-nb-secondary font-medium text-sm hover:bg-nb-elevated hover:text-nb-text transition-colors"
          >
            Ver como funciona
          </a>
        </div>

        {/* Product mockup */}
        <div className="mt-16 max-w-4xl mx-auto">
          <div className="rounded-2xl border border-nb-border bg-nb-surface overflow-hidden shadow-2xl">
            <div className="flex items-center gap-1.5 px-4 py-3 bg-nb-panel border-b border-nb-border">
              <span className="w-3 h-3 rounded-full bg-nb-soft" />
              <span className="w-3 h-3 rounded-full bg-nb-soft" />
              <span className="w-3 h-3 rounded-full bg-nb-soft" />
              <span className="ml-4 text-xs text-nb-muted">Wenzap — Painel operacional</span>
            </div>
            <div className="grid grid-cols-3 divide-x divide-nb-border min-h-[280px] md:min-h-[360px]">
              {/* Conversas */}
              <div className="p-4 flex flex-col gap-3">
                <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-wider">Conversas</p>
                {[
                  { name: "Carlos S.", msg: "Preciso de ajuda com meu pedido", ai: true },
                  { name: "Ana Lima", msg: "Quais planos vocês oferecem?", ai: true },
                  { name: "Marcos R.", msg: "Quero falar com um atendente", ai: false },
                ].map((c) => (
                  <div key={c.name} className="flex items-start gap-2 p-2 rounded-lg bg-nb-elevated">
                    <div className="w-7 h-7 rounded-full bg-nb-soft flex-shrink-0 flex items-center justify-center text-[10px] font-bold text-nb-secondary">
                      {c.name[0]}
                    </div>
                    <div className="min-w-0">
                      <p className="text-[11px] font-medium text-nb-text truncate">{c.name}</p>
                      <p className="text-[10px] text-nb-muted truncate">{c.msg}</p>
                    </div>
                    <span className={`ml-auto text-[9px] font-medium px-1.5 py-0.5 rounded-full flex-shrink-0 ${c.ai ? "bg-nb-primary-bg text-nb-primary" : "bg-nb-warning/10 text-nb-warning"}`}>
                      {c.ai ? "IA" : "Humano"}
                    </span>
                  </div>
                ))}
              </div>
              {/* Agente */}
              <div className="p-4 flex flex-col gap-3">
                <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-wider">Agente ativo</p>
                <div className="rounded-xl border border-nb-primary/20 bg-nb-primary-bg/30 p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="w-2 h-2 rounded-full bg-nb-primary" />
                    <span className="text-[11px] font-semibold text-nb-primary">Suporte respondendo</span>
                  </div>
                  <p className="text-[10px] text-nb-secondary leading-relaxed">
                    Consultando informações da empresa e apresentando opções ao cliente.
                  </p>
                </div>
                <div className="flex flex-col gap-1.5 mt-1">
                  {[
                    "Informações da empresa carregadas",
                    "Produtos disponíveis para recomendar",
                    "Conversas organizadas",
                  ].map((t) => (
                    <div key={t} className="flex items-center gap-2 text-[10px] text-nb-secondary">
                      <span className="w-1.5 h-1.5 rounded-full bg-nb-success" />
                      {t}
                    </div>
                  ))}
                </div>
              </div>
              {/* Métricas */}
              <div className="p-4 flex flex-col gap-3">
                <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-wider">Visão geral</p>
                {[
                  { label: "Conversas abertas", value: "24" },
                  { label: "Agentes ativos", value: "3" },
                  { label: "Canais conectados", value: "5" },
                  { label: "Itens disponíveis", value: "142" },
                ].map((m) => (
                  <div key={m.label} className="flex items-center justify-between p-2 rounded-lg bg-nb-elevated">
                    <span className="text-[10px] text-nb-muted">{m.label}</span>
                    <span className="text-[13px] font-bold text-nb-text">{m.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
