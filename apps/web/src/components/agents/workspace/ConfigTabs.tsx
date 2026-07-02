export type ConfigTab = "geral" | "instrucoes" | "comportamento" | "modelo" | "pipeline";

const TABS: { id: ConfigTab; label: string }[] = [
  { id: "geral",          label: "Geral" },
  { id: "instrucoes",     label: "Instruções" },
  { id: "comportamento",  label: "Comportamento" },
  { id: "modelo",         label: "Modelo" },
  { id: "pipeline",       label: "Pipeline" },
];

export function ConfigTabs({
  active,
  onChange,
}: {
  active: ConfigTab;
  onChange: (tab: ConfigTab) => void;
}) {
  return (
    <div className="border-b border-nb-border">
      <nav className="flex gap-0 -mb-px overflow-x-auto">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => onChange(id)}
            className={`
              flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors
              ${active === id
                ? "border-nb-primary text-nb-primary-strong"
                : "border-transparent text-nb-muted hover:text-nb-secondary hover:border-nb-border-strong"}
            `}
          >
            {label}
          </button>
        ))}
      </nav>
    </div>
  );
}
