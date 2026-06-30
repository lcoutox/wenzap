import { MessageSquare, Radio, Settings, Wrench } from "lucide-react";

export type WorkspaceTab = "chat" | "deploy" | "settings" | "knowledge" | "tools";

const TABS: { id: WorkspaceTab; label: string; icon: React.ElementType }[] = [
  { id: "chat",     label: "Chat",          icon: MessageSquare },
  { id: "deploy",   label: "Canais",        icon: Radio },
  { id: "tools",    label: "Ferramentas",   icon: Wrench },
  { id: "settings", label: "Configurações", icon: Settings },
];

export function AgentWorkspaceTabs({
  active,
  onChange,
}: {
  active: WorkspaceTab;
  onChange: (tab: WorkspaceTab) => void;
}) {
  return (
    <div className="border-b border-nb-border bg-nb-surface">
      <nav className="flex gap-0 -mb-px">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => onChange(id)}
            className={`
              flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors
              ${active === id
                ? "border-nb-primary text-nb-primary-strong"
                : "border-transparent text-nb-muted hover:text-nb-secondary hover:border-nb-border-strong"}
            `}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </nav>
    </div>
  );
}
