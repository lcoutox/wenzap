"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Bot,
  Check,
  ChevronRight,
  MessageSquare,
  Package,
  Plus,
  Radio,
  Upload,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Agent, Channel, Conversation, KnowledgeBase } from "@/lib/api";
import { useAppAuth } from "@/contexts/AuthContext";

// ── Types ─────────────────────────────────────────────────────────────────────

interface OverviewData {
  agents: Agent[];
  channels: Channel[];
  knowledgeBases: KnowledgeBase[];
  openConversations: Conversation[];
  activeCatalogItemCount: number;
}

// ── Metric card ───────────────────────────────────────────────────────────────

function MetricCard({
  icon: Icon,
  label,
  value,
  href,
  accent,
}: {
  icon: React.ElementType;
  label: string;
  value: number | string;
  href: string;
  accent?: boolean;
}) {
  return (
    <Link
      href={href}
      className="bg-nb-panel rounded-2xl border border-nb-border p-5 hover:border-nb-border-strong transition-all group flex flex-col gap-3"
    >
      <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${
        accent
          ? "bg-nb-primary/10 border border-nb-primary/20"
          : "bg-nb-elevated border border-nb-border"
      }`}>
        <Icon className={`w-4 h-4 ${accent ? "text-nb-primary-strong" : "text-nb-muted"}`} />
      </div>
      <div>
        <p className="text-2xl font-bold text-nb-text">{value}</p>
        <p className="text-xs text-nb-muted mt-0.5">{label}</p>
      </div>
    </Link>
  );
}

// ── Checklist item ────────────────────────────────────────────────────────────

function ChecklistItem({
  done,
  title,
  description,
  ctaLabel,
  ctaHref,
}: {
  done: boolean;
  title: string;
  description?: string;
  ctaLabel?: string;
  ctaHref?: string;
}) {
  return (
    <div className={`flex items-start gap-3 p-4 rounded-xl border transition-colors ${
      done ? "border-nb-border bg-nb-elevated/50" : "border-nb-border bg-nb-panel"
    }`}>
      <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
        done
          ? "bg-nb-success/20 border border-nb-success/30"
          : "border-2 border-nb-border-strong"
      }`}>
        {done && <Check className="w-3 h-3 text-nb-success" />}
      </div>
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium ${done ? "text-nb-muted line-through" : "text-nb-text"}`}>
          {title}
        </p>
        {!done && description && (
          <p className="text-xs text-nb-muted mt-0.5 leading-relaxed">{description}</p>
        )}
        {!done && ctaLabel && ctaHref && (
          <Link
            href={ctaHref}
            className="inline-flex items-center gap-1 mt-2 text-xs font-medium text-nb-primary hover:text-nb-primary-strong transition-colors"
          >
            {ctaLabel}
            <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        )}
      </div>
    </div>
  );
}

// ── Alert banner ──────────────────────────────────────────────────────────────

function AlertBanner({ title, description, href, ctaLabel }: {
  title: string;
  description: string;
  href: string;
  ctaLabel: string;
}) {
  return (
    <div className="flex items-start gap-3 p-3.5 rounded-xl border border-nb-warning/30 bg-nb-warning/5">
      <AlertTriangle className="w-4 h-4 text-nb-warning flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-nb-text">{title}</p>
        <p className="text-xs text-nb-muted mt-0.5">{description}</p>
      </div>
      <Link
        href={href}
        className="flex-shrink-0 text-xs font-medium text-nb-warning hover:text-nb-warning/80 transition-colors"
      >
        {ctaLabel}
      </Link>
    </div>
  );
}

// ── Agent row ─────────────────────────────────────────────────────────────────

function AgentRow({
  agent,
  channelCount,
}: {
  agent: Agent;
  channelCount: number;
}) {
  const statusColors: Record<string, string> = {
    active:   "bg-nb-success text-nb-success",
    inactive: "bg-nb-muted text-nb-muted",
    draft:    "bg-nb-warning text-nb-warning",
    archived: "bg-nb-danger text-nb-danger",
  };
  const statusLabels: Record<string, string> = {
    active:   "Ativo",
    inactive: "Inativo",
    draft:    "Rascunho",
    archived: "Arquivado",
  };

  const dotColor = statusColors[agent.status]?.split(" ")[0] ?? "bg-nb-muted";
  const statusLabel = statusLabels[agent.status] ?? agent.status;

  return (
    <div className="flex items-center gap-3 py-3 border-b border-nb-border last:border-0">
      <div className="w-8 h-8 rounded-xl bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
        <Bot className="w-4 h-4 text-nb-primary-strong" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-nb-text truncate">{agent.name}</span>
          <span className="flex items-center gap-1 text-xs text-nb-muted">
            <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
            {statusLabel}
          </span>
        </div>
        <div className="flex items-center gap-2 mt-0.5 flex-wrap text-xs text-nb-muted">
          <span>{agent.model_name}</span>
          <span>·</span>
          <span>{channelCount > 0 ? `${channelCount} ${channelCount === 1 ? "canal" : "canais"}` : "Sem canal"}</span>
          {agent.catalog_enabled && (
            <>
              <span>·</span>
              <span className="text-nb-success">Catálogo ativo</span>
            </>
          )}
        </div>
      </div>
      <Link
        href={`/dashboard/agents/${agent.id}`}
        className="flex-shrink-0 flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
      >
        Abrir
        <ChevronRight className="w-3 h-3" />
      </Link>
    </div>
  );
}

// ── Main dashboard content ────────────────────────────────────────────────────

function DashboardContent() {
  const { workspace } = useAppAuth();
  const [data, setData]     = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.agents.list(),
      api.channels.list(),
      api.knowledgeBases.list(),
      api.conversations.list({ status: "open", limit: 100 }),
      api.catalog.items.list({ status: "active", limit: 200 }),
    ])
      .then(([agents, channels, kbs, conversations, catalogItems]) => {
        setData({
          agents,
          channels,
          knowledgeBases: kbs,
          openConversations: conversations,
          activeCatalogItemCount: catalogItems.length,
        });
      })
      .catch(() => setError("Não foi possível carregar a visão geral."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-16 bg-nb-panel rounded-2xl border border-nb-border" />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {[...Array(5)].map((_, i) => <div key={i} className="h-28 bg-nb-panel rounded-2xl border border-nb-border" />)}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="h-64 bg-nb-panel rounded-2xl border border-nb-border" />
          <div className="h-64 bg-nb-panel rounded-2xl border border-nb-border" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-4 bg-nb-danger/10 border border-nb-danger/20 rounded-xl text-sm text-nb-danger">
        {error ?? "Erro desconhecido."}
      </div>
    );
  }

  // ── Derivations ────────────────────────────────────────────────────────────

  const activeAgents    = data.agents.filter((a) => a.status === "active");
  const activeChannels  = data.channels.filter((c) => c.status === "active");
  const activeKbs       = data.knowledgeBases.filter((kb) => kb.status === "active");
  const openCount       = data.openConversations.length;
  const pendingHuman    = data.openConversations.filter((c) => !c.ai_enabled).length;

  // Channels per agent
  const channelsByAgent: Record<string, number> = {};
  for (const ch of data.channels) {
    channelsByAgent[ch.agent_id] = (channelsByAgent[ch.agent_id] ?? 0) + 1;
  }

  // Activation checklist
  const hasAgent          = data.agents.length > 0;
  const hasKnowledge      = activeKbs.length > 0;
  const hasCatalogItems   = data.activeCatalogItemCount > 0;
  const hasChannel        = activeChannels.length > 0;
  const checklist = [
    {
      done: hasAgent,
      title: "Criar agente",
      description: "Configure o primeiro agente de IA da sua operação.",
      ctaLabel: "Criar agente",
      ctaHref: "/dashboard/agents/new",
    },
    {
      done: hasKnowledge,
      title: "Adicionar conhecimento",
      description: "Conecte documentos e FAQs para melhorar as respostas da IA.",
      ctaLabel: "Adicionar conhecimento",
      ctaHref: "/dashboard/knowledge-bases",
    },
    {
      done: hasCatalogItems,
      title: "Configurar Catálogo",
      description: "Adicione produtos e serviços que o agente pode recomendar.",
      ctaLabel: "Ir ao Catálogo",
      ctaHref: "/dashboard/catalog",
    },
    {
      done: hasChannel,
      title: "Conectar canal",
      description: "Conecte WhatsApp ou Web Widget para receber conversas.",
      ctaLabel: "Conectar canal",
      ctaHref: data.agents.length > 0
        ? `/dashboard/agents/${data.agents[0].id}?tab=deploy`
        : "/dashboard/agents/new",
    },
    {
      done: false,
      title: "Testar agente",
      description: "Teste como seu agente responde antes de publicar.",
      ctaLabel: "Testar agente",
      ctaHref: data.agents.length > 0
        ? `/dashboard/agents/${data.agents[0].id}?tab=chat`
        : "/dashboard/agents/new",
    },
  ];

  const completedSteps = checklist.filter((c) => c.done).length;
  const allDone = completedSteps === checklist.length;

  // Alerts (max 3, prioritized)
  const alerts: { title: string; description: string; href: string; ctaLabel: string }[] = [];
  if (activeAgents.length === 0 && data.agents.length > 0) {
    alerts.push({
      title: "Nenhum agente ativo",
      description: "Você tem agentes criados mas nenhum está ativo. Ative um agente para começar.",
      href: `/dashboard/agents/${data.agents[0].id}`,
      ctaLabel: "Ver agentes",
    });
  }
  if (activeAgents.length > 0 && activeChannels.length === 0) {
    alerts.push({
      title: "Nenhum canal conectado",
      description: "Seus agentes estão ativos mas não há canal para receber conversas.",
      href: data.agents.length > 0
        ? `/dashboard/agents/${data.agents[0].id}?tab=deploy`
        : "/dashboard/agents",
      ctaLabel: "Conectar canal",
    });
  }
  if (activeAgents.length > 0 && activeKbs.length === 0) {
    alerts.push({
      title: "Nenhuma base de conhecimento conectada",
      description: "Adicione documentos e FAQs para que o agente responda com mais precisão.",
      href: "/dashboard/knowledge-bases",
      ctaLabel: "Adicionar",
    });
  }
  if (hasCatalogItems === false && activeAgents.some((a) => a.catalog_enabled)) {
    alerts.push({
      title: "Catálogo vazio",
      description: "Um agente usa o Catálogo, mas não há itens cadastrados.",
      href: "/dashboard/catalog/new",
      ctaLabel: "Adicionar item",
    });
  }
  const visibleAlerts = alerts.slice(0, 3);

  // Quick actions
  const quickActions = [
    { label: "Criar agente", href: "/dashboard/agents/new", icon: Bot },
    { label: "Adicionar conhecimento", href: "/dashboard/knowledge-bases", icon: BookOpen },
    { label: "Novo item no Catálogo", href: "/dashboard/catalog/new", icon: Package },
    { label: "Importar Catálogo", href: "/dashboard/catalog/import", icon: Upload },
    {
      label: "Conectar canal",
      href: data.agents.length > 0
        ? `/dashboard/agents/${data.agents[0].id}?tab=deploy`
        : "/dashboard/agents/new",
      icon: Radio,
    },
  ];

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-8">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-nb-text">Visão geral</h1>
        <p className="mt-0.5 text-sm text-nb-muted">
          Acompanhe o estado da sua operação em{" "}
          <span className="font-medium text-nb-secondary">{workspace?.name}</span>.
        </p>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        <MetricCard
          icon={Bot}
          label="Agentes ativos"
          value={activeAgents.length}
          href="/dashboard/agents"
          accent={activeAgents.length > 0}
        />
        <MetricCard
          icon={Radio}
          label="Canais conectados"
          value={activeChannels.length}
          href="/dashboard/agents"
          accent={activeChannels.length > 0}
        />
        <MetricCard
          icon={MessageSquare}
          label="Conversas abertas"
          value={openCount >= 100 ? "100+" : openCount}
          href="/dashboard/inbox"
          accent={openCount > 0}
        />
        <MetricCard
          icon={BookOpen}
          label="Bases de conhecimento"
          value={activeKbs.length}
          href="/dashboard/knowledge-bases"
          accent={activeKbs.length > 0}
        />
        <MetricCard
          icon={Package}
          label="Itens no Catálogo"
          value={data.activeCatalogItemCount >= 200 ? "200+" : data.activeCatalogItemCount}
          href="/dashboard/catalog"
          accent={data.activeCatalogItemCount > 0}
        />
      </div>

      {/* Alerts */}
      {visibleAlerts.length > 0 && (
        <div className="flex flex-col gap-3">
          <p className="text-xs font-semibold text-nb-muted uppercase tracking-wide">
            Atenção necessária
          </p>
          <div className="flex flex-col gap-2">
            {visibleAlerts.map((a, i) => (
              <AlertBanner key={i} {...a} />
            ))}
          </div>
        </div>
      )}

      {/* Main two-column grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Left: checklist + quick actions */}
        <div className="flex flex-col gap-6">

          {/* Checklist */}
          <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 flex flex-col gap-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-nb-text">Configure sua operação</h2>
                <p className="text-xs text-nb-muted mt-0.5">
                  {allDone
                    ? "Todos os passos concluídos. Sua operação está pronta."
                    : `${completedSteps} de ${checklist.length} passos concluídos.`}
                </p>
              </div>
              {!allDone && (
                <span className="flex-shrink-0 px-2.5 py-1 rounded-full bg-nb-primary/10 border border-nb-primary/20 text-xs font-semibold text-nb-primary">
                  {completedSteps}/{checklist.length}
                </span>
              )}
              {allDone && (
                <div className="w-7 h-7 rounded-full bg-nb-success/20 border border-nb-success/30 flex items-center justify-center flex-shrink-0">
                  <Check className="w-4 h-4 text-nb-success" />
                </div>
              )}
            </div>

            {/* Progress bar */}
            <div className="h-1.5 rounded-full bg-nb-elevated overflow-hidden">
              <div
                className="h-full rounded-full bg-nb-primary transition-all"
                style={{ width: `${(completedSteps / checklist.length) * 100}%` }}
              />
            </div>

            <div className="flex flex-col gap-2">
              {checklist.map((item, i) => (
                <ChecklistItem key={i} {...item} />
              ))}
            </div>
          </div>

          {/* Quick actions */}
          <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 flex flex-col gap-4">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-nb-primary" />
              <h2 className="text-sm font-semibold text-nb-text">Ações rápidas</h2>
            </div>
            <div className="flex flex-col gap-1">
              {quickActions.map(({ label, href, icon: Icon }) => (
                <Link
                  key={href}
                  href={href}
                  className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-nb-elevated transition-colors group"
                >
                  <div className="w-7 h-7 rounded-lg bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0 group-hover:border-nb-primary/30 group-hover:bg-nb-primary/5 transition-colors">
                    <Icon className="w-3.5 h-3.5 text-nb-muted group-hover:text-nb-primary transition-colors" />
                  </div>
                  <span className="text-sm text-nb-secondary group-hover:text-nb-text transition-colors">
                    {label}
                  </span>
                  <ChevronRight className="w-3.5 h-3.5 text-nb-muted ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Right: agents */}
        <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-nb-text">Seus agentes</h2>
            <Link
              href="/dashboard/agents"
              className="text-xs text-nb-primary hover:text-nb-primary-strong transition-colors"
            >
              Ver todos →
            </Link>
          </div>

          {pendingHuman > 0 && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-nb-warning/10 border border-nb-warning/20 text-xs text-nb-warning">
              <MessageSquare className="w-3.5 h-3.5 flex-shrink-0" />
              <span>
                <span className="font-semibold">{pendingHuman}</span>{" "}
                {pendingHuman === 1 ? "conversa aguardando" : "conversas aguardando"} atendimento humano
              </span>
              <Link href="/dashboard/inbox" className="ml-auto font-medium hover:underline">
                Ver →
              </Link>
            </div>
          )}

          {data.agents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-nb-elevated border border-nb-border flex items-center justify-center">
                <Bot className="w-6 h-6 text-nb-muted" />
              </div>
              <div>
                <p className="text-sm font-medium text-nb-text">Nenhum agente criado.</p>
                <p className="text-xs text-nb-muted mt-0.5">
                  Crie seu primeiro agente para começar sua operação com IA.
                </p>
              </div>
              <Link
                href="/dashboard/agents/new"
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-nb-primary text-white text-xs font-medium hover:bg-nb-primary-strong transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                Criar agente
              </Link>
            </div>
          ) : (
            <div>
              {data.agents.slice(0, 5).map((agent) => (
                <AgentRow
                  key={agent.id}
                  agent={agent}
                  channelCount={channelsByAgent[agent.id] ?? 0}
                />
              ))}
              {data.agents.length > 5 && (
                <div className="pt-3 text-center">
                  <Link
                    href="/dashboard/agents"
                    className="text-xs text-nb-muted hover:text-nb-primary transition-colors"
                  >
                    + {data.agents.length - 5} agente{data.agents.length - 5 !== 1 ? "s" : ""} não exibidos
                  </Link>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Page (Suspense wrapper for future useSearchParams if needed) ───────────────

export default function DashboardPage() {
  return (
    <Suspense>
      <DashboardContent />
    </Suspense>
  );
}
