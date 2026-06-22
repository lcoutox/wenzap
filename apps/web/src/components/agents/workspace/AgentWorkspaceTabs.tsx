import { MessageSquare, Radio, Settings } from "lucide-react";

export type WorkspaceTab = "chat" | "deploy" | "settings";

const TABS: { id: WorkspaceTab; label: string; icon: React.ElementType }[] = [
  { id: "chat",     label: "Chat",          icon: MessageSquare },
  { id: "deploy",   label: "Implantar",     icon: Radio },
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
    <div className="border-b border-gray-200 bg-white">
      <nav className="flex gap-0 -mb-px">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => onChange(id)}
            className={`
              flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors
              ${active === id
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }
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
