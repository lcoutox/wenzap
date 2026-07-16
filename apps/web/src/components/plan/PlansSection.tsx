"use client";

import { useEffect, useState } from "react";
import { Check, ExternalLink, Loader2, Tag, X, Zap } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { CouponValidation, MemberRole, Plan, Subscription } from "@/lib/api";
import { planAllowsFeature } from "@/lib/plan";

// ── Feature comparison (numeric limits are read from the real Plan records;
// boolean feature flags mirror the same FEATURE_MIN_PLAN table the backend
// enforces, in lib/plan.ts) ────────────────────────────────────────────────

const BOOLEAN_FEATURES: { key: string; label: string }[] = [
  { key: "whatsapp_channel", label: "WhatsApp Business" },
  { key: "pipelines", label: "Pipelines" },
  { key: "integrations", label: "Integrações" },
  { key: "multiple_knowledge_bases", label: "Múltiplas bases de conhecimento" },
];

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

function formatBRL(cents: number): string {
  return (cents / 100).toLocaleString("pt-BR", { minimumFractionDigits: cents % 100 ? 2 : 0 });
}

// ── Coupon field ──────────────────────────────────────────────────────────────

function CouponField({
  planCode,
  onApplied,
}: {
  planCode: string;
  onApplied: (result: CouponValidation | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CouponValidation | null>(null);

  async function apply() {
    if (!code.trim()) return;
    setLoading(true);
    try {
      const res = await api.billing.validateCoupon(code.trim(), planCode);
      setResult(res);
      onApplied(res.valid ? res : null);
    } catch {
      setResult({ valid: false, error: "Erro ao validar cupom" });
      onApplied(null);
    } finally {
      setLoading(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full flex items-center justify-center gap-1.5 text-[11px] font-medium text-nb-muted hover:text-nb-secondary transition-colors"
      >
        <Tag className="w-3 h-3" />
        Tenho um cupom de desconto
      </button>
    );
  }

  return (
    <div className="space-y-1.5">
      <div className="flex gap-1.5">
        <input
          type="text"
          value={code}
          onChange={(e) => { setCode(e.target.value.toUpperCase()); setResult(null); onApplied(null); }}
          placeholder="CÓDIGO"
          className="flex-1 min-w-0 bg-nb-elevated border border-nb-border rounded-lg px-2.5 py-1.5 text-xs text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary transition-colors"
        />
        <button
          type="button"
          onClick={apply}
          disabled={loading || !code.trim()}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-nb-elevated border border-nb-border text-nb-secondary hover:text-nb-text disabled:opacity-40 transition-colors"
        >
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : "Aplicar"}
        </button>
      </div>
      {result && !result.valid && (
        <p className="text-[11px] text-nb-danger">{result.error ?? "Cupom inválido"}</p>
      )}
      {result?.valid && (
        <p className="text-[11px] text-nb-success">
          Cupom aplicado — de R${formatBRL(result.original_price_cents ?? 0)} por{" "}
          <strong>R${formatBRL(result.discounted_price_cents ?? 0)}</strong>/mês
        </p>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function PlansSection({ subscription }: { subscription: Subscription | null }) {
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [role, setRole] = useState<MemberRole | null>(null);
  const [appliedCoupon, setAppliedCoupon] = useState<CouponValidation | null>(null);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [portalLoading, setPortalLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    api.plans.list().then(setPlans).catch(() => setPlans([]));
    api.me().then((me) => setRole(me.role)).catch(() => {});
  }, []);

  const currentPlanCode = subscription?.plan?.code ?? "starter";
  const isPaying = currentPlanCode !== "starter";
  const canManageBilling = role === "owner" || role === "admin";

  const freePlan = plans?.find((p) => p.code === "starter");
  const growthPlan = plans?.find((p) => p.code === "growth");

  async function handleSubscribe() {
    if (!growthPlan) return;
    setActionError(null);
    setCheckoutLoading(true);
    try {
      const { checkout_url } = await api.billing.checkoutSession(
        growthPlan.code,
        appliedCoupon?.valid ? appliedCoupon.code ?? undefined : undefined
      );
      window.location.href = checkout_url;
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Não foi possível iniciar o checkout. Tente novamente."
      );
      setCheckoutLoading(false);
    }
  }

  async function handleManageBilling() {
    setActionError(null);
    setPortalLoading(true);
    try {
      const { portal_url } = await api.billing.portalSession();
      window.location.href = portal_url;
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Não foi possível abrir o portal de faturamento."
      );
      setPortalLoading(false);
    }
  }

  if (plans === null) {
    return <div className="h-40 flex items-center justify-center text-sm text-nb-muted">Carregando planos…</div>;
  }

  return (
    <div className="max-w-2xl space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-nb-text">Planos disponíveis</h2>
        <p className="text-xs text-nb-muted mt-0.5">Compare Free e Growth para escolher o melhor para sua operação.</p>
      </div>

      {actionError && (
        <div className="rounded-xl border border-nb-danger/20 bg-nb-danger/5 p-3">
          <p className="text-xs text-nb-danger">{actionError}</p>
        </div>
      )}

      {!canManageBilling && (
        <div className="rounded-xl border border-nb-border bg-nb-elevated/30 p-3">
          <p className="text-xs text-nb-muted">
            Apenas administradores do workspace podem gerenciar a assinatura.
          </p>
        </div>
      )}

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
            <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />{freePlan?.agents_limit ?? 1} agente</li>
            <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />{freePlan?.knowledge_bases_limit ?? 1} base de conhecimento</li>
            <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />Web Widget</li>
            <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />{(freePlan?.monthly_ai_credits ?? 0).toLocaleString("pt-BR")} créditos IA/mês</li>
            <li className="flex items-center gap-2"><X className="w-3.5 h-3.5 text-nb-muted/50 flex-shrink-0" /><span className="text-nb-muted">WhatsApp</span></li>
          </ul>

          {currentPlanCode === "starter" && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-lg text-[10px] font-bold bg-nb-primary-bg border border-nb-primary/20 text-nb-primary-strong uppercase tracking-widest">
              Plano atual
            </span>
          )}
        </div>

        {/* Growth */}
        <div className={`rounded-2xl border p-5 space-y-4 ${isPaying ? "border-nb-primary/30 bg-nb-primary-bg/30" : "border-nb-border bg-nb-panel"}`}>
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2">
                <p className="text-sm font-bold text-nb-text">Growth</p>
                <span className="text-[9px] font-bold px-1.5 py-0.5 bg-nb-warning/10 border border-nb-warning/30 text-nb-warning rounded uppercase tracking-widest">Popular</span>
              </div>
              <p className="text-xs text-nb-muted mt-0.5">Para operar com agentes de IA</p>
            </div>
            <div className="text-right">
              <p className="text-lg font-bold text-nb-text">R${formatBRL(growthPlan?.monthly_price_cents ?? 24700)}</p>
              <p className="text-[10px] text-nb-muted">/mês</p>
            </div>
          </div>

          <ul className="space-y-1.5 text-xs text-nb-secondary">
            <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />{growthPlan?.agents_limit ?? 3} agentes</li>
            <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />{growthPlan?.knowledge_bases_limit ?? 5} bases de conhecimento</li>
            <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />Web Widget + <strong>WhatsApp</strong></li>
            <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />{(growthPlan?.monthly_ai_credits ?? 7500).toLocaleString("pt-BR")} créditos IA/mês</li>
            <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />{growthPlan?.catalog_items_limit ?? 500} itens no Catálogo</li>
            <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />{growthPlan?.users_limit ?? 5} usuários · {growthPlan?.channels_limit ?? 5} canais</li>
          </ul>

          {isPaying ? (
            <>
              <span className="inline-flex items-center px-2.5 py-1 rounded-lg text-[10px] font-bold bg-nb-primary-bg border border-nb-primary/20 text-nb-primary-strong uppercase tracking-widest">
                Plano atual
              </span>
              {canManageBilling && (
                <button
                  type="button"
                  onClick={handleManageBilling}
                  disabled={portalLoading}
                  className="w-full flex items-center justify-center gap-1.5 py-2 rounded-xl text-sm font-semibold bg-nb-elevated border border-nb-border text-nb-secondary hover:text-nb-text disabled:opacity-40 transition-colors"
                >
                  {portalLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ExternalLink className="w-3.5 h-3.5" />}
                  Gerenciar assinatura
                </button>
              )}
            </>
          ) : canManageBilling ? (
            <div className="space-y-2.5">
              <button
                type="button"
                onClick={handleSubscribe}
                disabled={checkoutLoading || !growthPlan}
                className="w-full flex items-center justify-center gap-1.5 py-2 rounded-xl text-sm font-semibold bg-nb-primary text-white hover:bg-nb-primary-strong disabled:opacity-40 transition-colors"
              >
                {checkoutLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
                Assinar Growth
              </button>
              <CouponField planCode="growth" onApplied={setAppliedCoupon} />
            </div>
          ) : null}
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
              <FeatureRow label="Agentes"               free={String(freePlan?.agents_limit ?? "—")}             growth={String(growthPlan?.agents_limit ?? "—")} />
              <FeatureRow label="Usuários"              free={String(freePlan?.users_limit ?? "—")}              growth={String(growthPlan?.users_limit ?? "—")} />
              <FeatureRow label="Bases de conhecimento" free={String(freePlan?.knowledge_bases_limit ?? "—")}    growth={String(growthPlan?.knowledge_bases_limit ?? "—")} />
              <FeatureRow label="Itens no Catálogo"     free={String(freePlan?.catalog_items_limit ?? "—")}      growth={String(growthPlan?.catalog_items_limit ?? "—")} />
              <FeatureRow label="Canais"                free={String(freePlan?.channels_limit ?? "—")}          growth={String(growthPlan?.channels_limit ?? "—")} />
              <FeatureRow label="Créditos IA/mês"       free={(freePlan?.monthly_ai_credits ?? 0).toLocaleString("pt-BR")} growth={(growthPlan?.monthly_ai_credits ?? 0).toLocaleString("pt-BR")} />
              {BOOLEAN_FEATURES.map(({ key, label }) => (
                <FeatureRow
                  key={key}
                  label={label}
                  free={planAllowsFeature("starter", key)}
                  growth={planAllowsFeature("growth", key)}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Sales-assisted tiers */}
      <div className="rounded-xl border border-nb-border bg-nb-elevated/30 p-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-nb-text">Precisa de mais? Scale e Enterprise</p>
          <p className="text-[11px] text-nb-muted mt-0.5">Limites maiores e suporte dedicado — fale com o time.</p>
        </div>
        <a
          href="mailto:growth@wenzap.com.br"
          className="flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-nb-panel border border-nb-border text-nb-secondary hover:text-nb-text transition-colors"
        >
          Falar com o time
        </a>
      </div>
    </div>
  );
}
