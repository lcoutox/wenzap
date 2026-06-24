export type ConfigTab =
  | "geral"
  | "prompt"
  | "modelo"
  | "avancado"
  | "ferramentas"
  | "seguranca"
  | "webhooks";

const TABS: { id: ConfigTab; label: string; placeholder?: true }[] = [
  { id: "geral",       label: "Geral" },
  { id: "prompt",      label: "Prompt" },
  { id: "modelo",      label: "Modelo" },
  { id: "avancado",    label: "Avançado" },
  { id: "ferramentas", label: "Ferramentas", placeholder: true },
  { id: "seguranca",   label: "Segurança",   placeholder: true },
  { id: "webhooks",    label: "Webhooks",    placeholder: true },
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
        {TABS.map(({ id, label, placeholder }) => (
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
            {placeholder && (
              <span className="px-1.5 py-0.5 text-[9px] font-bold rounded bg-nb-elevated text-nb-muted border border-nb-border leading-none tracking-wide">
                EM BREVE
              </span>
            )}
          </button>
        ))}
      </nav>
    </div>
  );
}
