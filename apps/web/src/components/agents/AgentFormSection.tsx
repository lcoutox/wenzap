export function AgentFormSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-nb-panel rounded-2xl border border-nb-border overflow-hidden">
      <div className="px-6 py-4 border-b border-nb-border bg-nb-elevated/50">
        <h3 className="text-sm font-semibold text-nb-text">{title}</h3>
        {description && <p className="text-xs text-nb-muted mt-0.5">{description}</p>}
      </div>
      <div className="p-6 space-y-5">{children}</div>
    </div>
  );
}
