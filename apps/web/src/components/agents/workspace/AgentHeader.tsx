import Link from "next/link";
import { Bot, ChevronRight, Coins } from "lucide-react";
import { api } from "@/lib/api";
import { AgentStatusBadge } from "@/components/agents/AgentStatusBadge";
import type { Agent, AiModel, MemberRole, AgentStatus } from "@/lib/api";

// ── Shared input style ────────────────────────────────────────────────────────

export const inputCls =
  "w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors";

export const disabledInputCls =
  "w-full bg-nb-bg border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-muted cursor-not-allowed";

// ── Action button ─────────────────────────────────────────────────────────────

function ActionButton({
  onClick,
  variant,
  children,
}: {
  onClick: () => void;
  variant: "primary" | "secondary" | "danger";
  children: React.ReactNode;
}) {
  const cls = {
    primary:   "bg-nb-primary text-white hover:bg-nb-primary-strong border-transparent",
    secondary: "bg-nb-elevated text-nb-secondary border-nb-border hover:bg-nb-soft hover:text-nb-text",
    danger:    "bg-nb-danger/10 text-nb-danger border-nb-danger/20 hover:bg-nb-danger/20",
  }[variant];
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-1.5 text-sm font-medium rounded-xl border transition-colors ${cls}`}
    >
      {children}
    </button>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export function AgentHeader({
  agent,
  activeModel,
  role,
  actionError,
  onChangeStatus,
  onArchive,
}: {
  agent: Agent;
  activeModel: AiModel | null;
  role: MemberRole | null;
  actionError: string | null;
  onChangeStatus: (s: AgentStatus) => void;
  onArchive: () => void;
}) {
  const isArchived = agent.status === "archived";
  const canWrite   = role === "owner" || role === "admin" || role === "member";
  const canArchive = role === "owner" || role === "admin";

  return (
    <div className="bg-nb-surface border-b border-nb-border px-6 py-5 space-y-4">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-sm text-nb-muted">
        <Link href="/dashboard/agents" className="hover:text-nb-secondary transition-colors">
          Agentes
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-nb-border-strong" />
        <span className="text-nb-secondary font-medium truncate max-w-xs">{agent.name}</span>
      </nav>

      {/* Agent identity row */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-4 min-w-0">
          {/* Avatar */}
          <div className="w-12 h-12 rounded-2xl bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center flex-shrink-0 overflow-hidden">
            {api.agents.resolveAvatarUrl(agent) ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={api.agents.resolveAvatarUrl(agent)!} alt={agent.name} className="w-full h-full object-cover" />
            ) : (
              <Bot className="w-6 h-6 text-nb-primary-strong" />
            )}
          </div>

          {/* Name + meta */}
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-nb-text leading-tight truncate">
              {agent.name}
            </h1>
            {agent.description && (
              <p className="text-sm text-nb-muted mt-0.5 line-clamp-1">{agent.description}</p>
            )}
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <AgentStatusBadge status={agent.status} />

              {activeModel ? (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-lg bg-nb-elevated text-nb-secondary border border-nb-border">
                  <span>{activeModel.display_name}</span>
                  {activeModel.credits_per_message > 0 && (
                    <>
                      <span className="text-nb-border-strong">·</span>
                      <Coins className="w-3 h-3 text-nb-warning" />
                      <span className="text-nb-warning">{activeModel.credits_per_message} cr.</span>
                    </>
                  )}
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 text-xs font-mono rounded-lg bg-nb-elevated text-nb-muted border border-nb-border">
                  {agent.model_name}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Action buttons */}
        {!isArchived && (
          <div className="flex items-center gap-2 flex-wrap flex-shrink-0">
            {agent.status === "draft" && canWrite && (
              <ActionButton variant="primary" onClick={() => onChangeStatus("active")}>
                Ativar agente
              </ActionButton>
            )}
            {agent.status === "active" && canWrite && (
              <ActionButton variant="secondary" onClick={() => onChangeStatus("inactive")}>
                Desativar
              </ActionButton>
            )}
            {agent.status === "inactive" && canWrite && (
              <ActionButton variant="primary" onClick={() => onChangeStatus("active")}>
                Reativar
              </ActionButton>
            )}
            {canArchive && (
              <ActionButton variant="danger" onClick={onArchive}>
                Arquivar
              </ActionButton>
            )}
          </div>
        )}
      </div>

      {/* Alerts */}
      {actionError && (
        <div className="p-3 bg-nb-danger/10 border border-nb-danger/20 rounded-xl text-sm text-nb-danger">
          {actionError}
        </div>
      )}
      {isArchived && (
        <div className="p-3 bg-nb-warning/10 border border-nb-warning/20 rounded-xl text-sm text-nb-warning">
          Este agente está arquivado e não pode ser editado.
        </div>
      )}
    </div>
  );
}
