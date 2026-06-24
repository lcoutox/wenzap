import type { AgentStatus } from "@/lib/api";

const CONFIG: Record<AgentStatus, { label: string; dot: string; cls: string }> = {
  draft:    { label: "Rascunho", dot: "bg-nb-muted",    cls: "bg-nb-elevated  text-nb-muted     border-nb-border"       },
  active:   { label: "Ativo",    dot: "bg-nb-success",  cls: "bg-nb-success/10 text-nb-success  border-nb-success/20"   },
  inactive: { label: "Inativo",  dot: "bg-nb-warning",  cls: "bg-nb-warning/10 text-nb-warning  border-nb-warning/20"   },
  archived: { label: "Arquivado",dot: "bg-nb-danger",   cls: "bg-nb-danger/10  text-nb-danger   border-nb-danger/20"    },
};

export function AgentStatusBadge({ status }: { status: AgentStatus }) {
  const { label, dot, cls } = CONFIG[status];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${cls}`}>
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dot}`} />
      {label}
    </span>
  );
}
