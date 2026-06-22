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
    <div className="border-b border-gray-200">
      <nav className="flex gap-0 -mb-px overflow-x-auto">
        {TABS.map(({ id, label, placeholder }) => (
          <button
            key={id}
            type="button"
            onClick={() => onChange(id)}
            className={`
              flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors
              ${active === id
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }
            `}
          >
            {label}
            {placeholder && (
              <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded bg-gray-100 text-gray-400 border border-gray-200 leading-none">
                EM BREVE
              </span>
            )}
          </button>
        ))}
      </nav>
    </div>
  );
}
