"use client";

import Link from "next/link";
import { ChevronRight, Sparkles, Wand2 } from "lucide-react";

export default function ChoosePath() {
  return (
    <div className="max-w-3xl space-y-6 pb-24">
      <nav className="flex items-center gap-1 text-sm text-nb-muted">
        <Link href="/dashboard/agents" className="hover:text-nb-secondary transition-colors">
          Agentes
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-nb-border-strong" />
        <span className="text-nb-secondary font-medium">Novo agente</span>
      </nav>

      <div className="space-y-3">
        <h1 className="text-2xl font-semibold text-nb-text">Como você quer criar?</h1>
        <p className="text-sm text-nb-muted">Escolha o caminho que melhor se adequa ao seu caso.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Template Path */}
        <Link
          href="/dashboard/agents/new/template"
          className="group relative overflow-hidden rounded-2xl border border-nb-border bg-nb-panel p-6 transition-all hover:border-nb-border-strong hover:bg-nb-elevated"
        >
          <div className="absolute inset-0 bg-gradient-to-br from-nb-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

          <div className="relative space-y-4">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-nb-primary/10 text-nb-primary">
              <Sparkles className="w-6 h-6" />
            </div>

            <div className="space-y-2">
              <h2 className="text-lg font-semibold text-nb-text">Usar Template</h2>
              <p className="text-sm text-nb-muted leading-relaxed">
                Comece com uma instrução pronta. Ideal para quem quer algo rápido e eficaz, sem perder tempo.
              </p>
            </div>

            <div className="flex items-center text-sm font-medium text-nb-primary group-hover:gap-2 transition-all">
              Continuar
              <ChevronRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-all" />
            </div>
          </div>
        </Link>

        {/* Advanced Path */}
        <Link
          href="/dashboard/agents/new/advanced"
          className="group relative overflow-hidden rounded-2xl border border-nb-border bg-nb-panel p-6 transition-all hover:border-nb-border-strong hover:bg-nb-elevated"
        >
          <div className="absolute inset-0 bg-gradient-to-br from-nb-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

          <div className="relative space-y-4">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-nb-primary/10 text-nb-primary">
              <Wand2 className="w-6 h-6" />
            </div>

            <div className="space-y-2">
              <h2 className="text-lg font-semibold text-nb-text">Criar do Zero</h2>
              <p className="text-sm text-nb-muted leading-relaxed">
                Você controla tudo. Ideal se sabe exatamente o que quer e quer customizar tudo.
              </p>
            </div>

            <div className="flex items-center text-sm font-medium text-nb-primary group-hover:gap-2 transition-all">
              Continuar
              <ChevronRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-all" />
            </div>
          </div>
        </Link>
      </div>

      <div className="rounded-2xl bg-nb-elevated border border-nb-border-strong p-4">
        <p className="text-sm text-nb-secondary">
          💡 <strong>Dica:</strong> Pode mudar de ideia depois. Você sempre pode editar as instruções do agente a qualquer momento.
        </p>
      </div>
    </div>
  );
}
