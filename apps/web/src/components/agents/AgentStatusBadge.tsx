import type { AgentStatus } from "@/lib/api";

const CONFIG: Record<AgentStatus, { label: string; className: string }> = {
  draft:    { label: "Rascunho", className: "bg-gray-100 text-gray-600 border-gray-200" },
  active:   { label: "Ativo",    className: "bg-green-50 text-green-700 border-green-200" },
  inactive: { label: "Inativo",  className: "bg-yellow-50 text-yellow-700 border-yellow-200" },
  archived: { label: "Arquivado",className: "bg-red-50 text-red-500 border-red-200" },
};

export function AgentStatusBadge({ status }: { status: AgentStatus }) {
  const { label, className } = CONFIG[status];
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${className}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
          status === "active" ? "bg-green-500" :
          status === "inactive" ? "bg-yellow-500" :
          status === "draft" ? "bg-gray-400" : "bg-red-400"
        }`}
      />
      {label}
    </span>
  );
}
