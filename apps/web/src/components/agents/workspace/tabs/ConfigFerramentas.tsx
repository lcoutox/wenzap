"use client";

import Link from "next/link";
import {
  BookOpen,
  Globe,
  Hand,
  CheckCircle2,
  Clock,
  ShoppingBag,
  ArrowRight,
} from "lucide-react";
import { SaveBar } from "@/components/agents/workspace/SaveBar";
import type { MemberRole } from "@/lib/api";

// ── Toggle ────────────────────────────────────────────────────────────────────

function Toggle({
  checked,
  disabled,
  onChange,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={`relative flex-shrink-0 w-10 h-6 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-nb-primary/40 ${
        checked ? "bg-nb-primary" : "bg-nb-border-strong"
      } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
    >
      <span
        className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${
          checked ? "translate-x-4" : "translate-x-0"
        }`}
      />
    </button>
  );
}

// ── Tool card ─────────────────────────────────────────────────────────────────

function ActiveToolCard({
  icon: Icon,
  name,
  description,
  badge,
  badgeColor,
  toggle,
  children,
}: {
  icon: React.ElementType;
  name: string;
  description: string;
  badge?: string;
  badgeColor?: "green" | "muted";
  toggle?: React.ReactNode;
  children?: React.ReactNode;
}) {
  const badgeCls =
    badgeColor === "green"
      ? "bg-nb-success/10 text-nb-success border-nb-success/20"
      : "bg-nb-elevated text-nb-muted border-nb-border";

  return (
    <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 flex flex-col gap-4">
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-xl bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
          <Icon className="w-5 h-5 text-nb-primary-strong" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-nb-text">{name}</h3>
            {badge && (
              <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${badgeCls}`}>
                {badge}
              </span>
            )}
          </div>
          <p className="text-xs text-nb-muted mt-1 leading-relaxed">{description}</p>
        </div>
        {toggle && <div className="shrink-0 mt-0.5">{toggle}</div>}
      </div>
      {children && <div className="border-t border-nb-border pt-3">{children}</div>}
    </div>
  );
}

function SoonToolCard({
  icon: Icon,
  name,
  description,
}: {
  icon: React.ElementType;
  name: string;
  description: string;
}) {
  return (
    <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 opacity-55">
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
          <Icon className="w-5 h-5 text-nb-muted" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-nb-secondary">{name}</h3>
            <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-nb-elevated border border-nb-border text-nb-muted">
              Em breve
            </span>
          </div>
          <p className="text-xs text-nb-muted mt-1 leading-relaxed">{description}</p>
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ConfigFerramentas({
  agentId,
  catalogEnabled,
  readonly,
  saving,
  saveError,
  saveSuccess,
  onCatalogEnabledChange,
}: {
  agentId: string;
  catalogEnabled: boolean;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onCatalogEnabledChange: (v: boolean) => void;
  role: MemberRole | null;
}) {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-base font-semibold text-nb-text">Ferramentas</h2>
        <p className="text-sm text-nb-muted mt-1 max-w-xl">
          Dê capacidades operacionais ao seu agente para consultar informações, usar o Catálogo e executar ações durante o atendimento.
        </p>
      </div>

      {/* Active tools */}
      <div className="space-y-3">
        <p className="text-xs font-semibold text-nb-muted uppercase tracking-wide">Ferramentas disponíveis</p>
        <div className="grid grid-cols-1 gap-4">

          {/* Knowledge Base */}
          <ActiveToolCard
            icon={BookOpen}
            name="Base de Conhecimento"
            description="Permite que o agente consulte documentos, perguntas frequentes e informações da empresa para responder com mais precisão."
            badge="Disponível"
            badgeColor="green"
          >
            <Link
              href={`/dashboard/agents/${agentId}?tab=knowledge`}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-nb-primary hover:text-nb-primary-strong transition-colors"
            >
              Gerenciar conhecimento
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </ActiveToolCard>

          {/* Catalog */}
          <ActiveToolCard
            icon={ShoppingBag}
            name="Catálogo"
            description="Permite que o agente consulte produtos, serviços, planos e ofertas cadastradas para recomendar opções durante o atendimento."
            badge={catalogEnabled ? "Ativo" : "Inativo"}
            badgeColor={catalogEnabled ? "green" : "muted"}
            toggle={
              <Toggle
                checked={catalogEnabled}
                disabled={readonly}
                onChange={onCatalogEnabledChange}
              />
            }
          >
            <div className="flex items-center justify-between flex-wrap gap-3">
              <p className="text-xs text-nb-muted">
                Quando ativado, o agente pode consultar itens ativos do Catálogo quando identificar uma intenção comercial.
              </p>
              <Link
                href="/dashboard/catalog"
                className="inline-flex items-center gap-1.5 text-xs font-medium text-nb-primary hover:text-nb-primary-strong transition-colors shrink-0"
              >
                Gerenciar Catálogo
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </ActiveToolCard>

        </div>
      </div>

      {/* SaveBar */}
      {!readonly && (
        <SaveBar saving={saving} saveError={saveError} saveSuccess={saveSuccess} />
      )}

      {/* Roadmap */}
      <div className="space-y-3">
        <p className="text-xs font-semibold text-nb-muted uppercase tracking-wide">Em breve</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <SoonToolCard
            icon={Globe}
            name="HTTP Tools"
            description="Permite que o agente consulte sistemas externos e execute ações via API durante o atendimento."
          />
          <SoonToolCard
            icon={Hand}
            name="Solicitar humano"
            description="Permite que o agente chame um atendente quando a conversa precisar de intervenção humana."
          />
          <SoonToolCard
            icon={Clock}
            name="Follow-up"
            description="Permite que o agente acompanhe oportunidades e retome conversas automaticamente."
          />
          <SoonToolCard
            icon={CheckCircle2}
            name="Marcar como resolvido"
            description="Permite que o agente finalize conversas quando o atendimento estiver concluído."
          />
        </div>
      </div>
    </div>
  );
}
