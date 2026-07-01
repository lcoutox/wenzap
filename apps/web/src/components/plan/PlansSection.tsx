"use client";

import { useState } from "react";
import { Check, X, Zap } from "lucide-react";
import type { Subscription } from "@/lib/api";

// ── Upgrade request modal ─────────────────────────────────────────────────────

function UpgradeRequestModal({ onClose }: { onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-nb-surface border border-nb-border rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center">
            <Zap className="w-5 h-5 text-nb-primary-strong" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-nb-text">Solicitar upgrade para Growth</h2>
            <p className="text-xs text-nb-muted mt-0.5">Ativação manual pela equipe Wenzap</p>
          </div>
        </div>

        <p className="text-sm text-nb-secondary leading-relaxed">
          O plano Growth ainda não possui checkout automático. Para ativar, entre em contato com a
          equipe Wenzap informando o e-mail da sua conta.
        </p>

        <div className="rounded-xl border border-nb-border bg-nb-elevated p-4 space-y-2">
          <p className="text-xs font-semibold text-nb-secondary uppercase tracking-wide">Formas de contato</p>
          <p className="text-sm text-nb-text">
            📧{" "}
            <a href="mailto:growth@wenzap.com.br" className="text-nb-primary hover:underline">
              growth@wenzap.com.br
            </a>
          </p>
          <p className="text-xs text-nb-muted">
            Resposta em até 1 dia útil. Cite o e-mail da sua conta para agilizar a ativação.
          </p>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="w-full py-2 rounded-xl text-sm font-medium bg-nb-elevated border border-nb-border text-nb-secondary hover:text-nb-text transition-colors"
        >
          Fechar
        </button>
      </div>
    </div>
  );
}

// ── Feature row ───────────────────────────────────────────────────────────────

function FeatureRow({
  label,
  free,
  growth,
}: {
  label: string;
  free: string | boolean;
  growth: string | boolean;
}) {
  function Cell({ value }: { value: string | boolean }) {
    if (typeof value === "boolean") {
      return value
        ? <Check className="w-4 h-4 text-nb-success mx-auto" />
        : <X className="w-4 h-4 text-nb-muted/40 mx-auto" />;
    }
    return <span className="text-xs text-nb-secondary">{value}</span>;
  }

  return (
    <tr className="border-t border-nb-border">
      <td className="py-2.5 pr-4 text-xs text-nb-secondary">{label}</td>
      <td className="py-2.5 px-4 text-center"><Cell value={free} /></td>
      <td className="py-2.5 px-4 text-center"><Cell value={growth} /></td>
    </tr>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function PlansSection({ subscription }: { subscription: Subscription | null }) {
  const [showModal, setShowModal] = useState(false);
  const currentPlanCode = subscription?.plan?.code ?? "starter";
  const isOnGrowth = currentPlanCode === "growth" || currentPlanCode === "scale" || currentPlanCode === "enterprise";

  return (
    <>
      {showModal && <UpgradeRequestModal onClose={() => setShowModal(false)} />}

      <div className="max-w-2xl space-y-4">
        <div>
          <h2 className="text-sm font-semibold text-nb-text">Planos disponíveis</h2>
          <p className="text-xs text-nb-muted mt-0.5">Compare Free e Growth para escolher o melhor para sua operação.</p>
        </div>

        {/* Plan cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Free */}
          <div className={`rounded-2xl border p-5 space-y-4 ${currentPlanCode === "starter" ? "border-nb-primary/30 bg-nb-primary-bg/30" : "border-nb-border bg-nb-panel"}`}>
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-bold text-nb-text">Free</p>
                <p className="text-xs text-nb-muted mt-0.5">Para testar o Wenzap</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-bold text-nb-text">R$0</p>
                <p className="text-[10px] text-nb-muted">/mês</p>
              </div>
            </div>

            <ul className="space-y-1.5 text-xs text-nb-secondary">
              <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />1 agente</li>
              <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />1 base de conhecimento</li>
              <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />Web Widget</li>
              <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />200 créditos IA/mês</li>
              <li className="flex items-center gap-2"><X className="w-3.5 h-3.5 text-nb-muted/50 flex-shrink-0" /><span className="text-nb-muted">WhatsApp</span></li>
            </ul>

            {currentPlanCode === "starter" && (
              <span className="inline-flex items-center px-2.5 py-1 rounded-lg text-[10px] font-bold bg-nb-primary-bg border border-nb-primary/20 text-nb-primary-strong uppercase tracking-widest">
                Plano atual
              </span>
            )}
          </div>

          {/* Growth */}
          <div className={`rounded-2xl border p-5 space-y-4 ${isOnGrowth ? "border-nb-primary/30 bg-nb-primary-bg/30" : "border-nb-border bg-nb-panel"}`}>
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-bold text-nb-text">Growth</p>
                  <span className="text-[9px] font-bold px-1.5 py-0.5 bg-nb-warning/10 border border-nb-warning/30 text-nb-warning rounded uppercase tracking-widest">Popular</span>
                </div>
                <p className="text-xs text-nb-muted mt-0.5">Para operar com agentes de IA</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-bold text-nb-text">R$297</p>
                <p className="text-[10px] text-nb-muted">/mês</p>
              </div>
            </div>

            <ul className="space-y-1.5 text-xs text-nb-secondary">
              <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />3 agentes</li>
              <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />5 bases de conhecimento</li>
              <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />Web Widget + <strong>WhatsApp</strong></li>
              <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />7.500 créditos IA/mês</li>
              <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />500 itens no Catálogo</li>
              <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />5 usuários · 5 canais</li>
            </ul>

            {isOnGrowth ? (
              <span className="inline-flex items-center px-2.5 py-1 rounded-lg text-[10px] font-bold bg-nb-primary-bg border border-nb-primary/20 text-nb-primary-strong uppercase tracking-widest">
                Plano atual
              </span>
            ) : (
              <button
                type="button"
                onClick={() => setShowModal(true)}
                className="w-full flex items-center justify-center gap-1.5 py-2 rounded-xl text-sm font-semibold bg-nb-primary text-white hover:bg-nb-primary-strong transition-colors"
              >
                <Zap className="w-3.5 h-3.5" />
                Solicitar upgrade
              </button>
            )}
          </div>
        </div>

        {/* Comparison table */}
        <div className="bg-nb-panel rounded-2xl border border-nb-border overflow-hidden">
          <div className="px-5 py-3 border-b border-nb-border">
            <p className="text-xs font-semibold text-nb-text">Comparativo detalhado</p>
          </div>
          <div className="px-5 pb-4 overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="py-3 pr-4 text-left text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Recurso</th>
                  <th className="py-3 px-4 text-center text-[10px] font-semibold text-nb-muted uppercase tracking-widest w-20">Free</th>
                  <th className="py-3 px-4 text-center text-[10px] font-semibold text-nb-primary uppercase tracking-widest w-20">Growth</th>
                </tr>
              </thead>
              <tbody>
                <FeatureRow label="Agentes"              free="1"       growth="3" />
                <FeatureRow label="Usuários"             free="1"       growth="5" />
                <FeatureRow label="Bases de conhecimento" free="1"      growth="5" />
                <FeatureRow label="Fontes por base"      free="10"      growth="100" />
                <FeatureRow label="Itens no Catálogo"    free="50"      growth="500" />
                <FeatureRow label="Canais"               free="1"       growth="5" />
                <FeatureRow label="Créditos IA/mês"      free="200"     growth="7.500" />
                <FeatureRow label="Tamanho máx. por arquivo" free="5 MB" growth="10 MB" />
                <FeatureRow label="Web Widget"           free={true}    growth={true} />
                <FeatureRow label="WhatsApp Business"    free={false}   growth={true} />
                <FeatureRow label="Catálogo de produtos" free={false}   growth={true} />
                <FeatureRow label="Pipelines"            free={false}   growth={true} />
                <FeatureRow label="HTTP Tools"           free={false}   growth={false} />
                <FeatureRow label="Webhooks"             free={false}   growth={false} />
                <FeatureRow label="Follow-up automático" free={false}   growth={false} />
                <FeatureRow label="Remover branding"     free={false}   growth={false} />
              </tbody>
            </table>
          </div>
        </div>

        <p className="text-[10px] text-nb-muted text-center">
          HTTP Tools, Webhooks e Follow-up automático estarão disponíveis em planos Scale e superiores.
        </p>
      </div>
    </>
  );
}
