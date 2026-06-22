import Link from "next/link";
import { Bot, ChevronRight, Coins, Wifi, WifiOff } from "lucide-react";
import { AgentStatusBadge } from "@/components/agents/AgentStatusBadge";
import type { Agent, AiModel, MemberRole, AgentStatus } from "@/lib/api";

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
    primary:   "bg-indigo-600 text-white hover:bg-indigo-700 border-transparent",
    secondary: "bg-white text-gray-700 border-gray-300 hover:bg-gray-50",
    danger:    "bg-white text-red-600 border-red-200 hover:bg-red-50",
  }[variant];
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors ${cls}`}
    >
      {children}
    </button>
  );
}

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
    <div className="bg-white border-b border-gray-200 px-6 py-5 space-y-4">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-sm text-gray-400">
        <Link href="/dashboard/agents" className="hover:text-gray-700 transition-colors">
          Agentes
        </Link>
        <ChevronRight className="w-3.5 h-3.5" />
        <span className="text-gray-700 font-medium truncate max-w-xs">{agent.name}</span>
      </nav>

      {/* Agent identity row */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-4 min-w-0">
          {/* Avatar */}
          <div className="w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center flex-shrink-0">
            <Bot className="w-6 h-6 text-indigo-500" />
          </div>

          {/* Name + meta */}
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-gray-900 leading-tight truncate">
              {agent.name}
            </h1>
            {agent.description && (
              <p className="text-sm text-gray-500 mt-0.5 line-clamp-1">{agent.description}</p>
            )}
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <AgentStatusBadge status={agent.status} />

              {activeModel ? (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-md bg-gray-100 text-gray-600 border border-gray-200">
                  <span>{activeModel.display_name}</span>
                  {activeModel.credits_per_message > 0 && (
                    <>
                      <span className="text-gray-300">·</span>
                      <Coins className="w-3 h-3 text-amber-500" />
                      <span className="text-amber-600">{activeModel.credits_per_message} crédito{activeModel.credits_per_message !== 1 ? "s" : ""}</span>
                    </>
                  )}
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 text-xs font-mono rounded-md bg-gray-100 text-gray-500 border border-gray-200">
                  {agent.model_name}
                </span>
              )}

              {/* Deploy status placeholder */}
              <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-md bg-yellow-50 text-yellow-600 border border-yellow-200">
                <WifiOff className="w-3 h-3" />
                Sem canal conectado
              </span>
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
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {actionError}
        </div>
      )}
      {isArchived && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">
          Este agente está arquivado e não pode ser editado.
        </div>
      )}
    </div>
  );
}
