const baseInput =
  "w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors";

export function StepIdentity({
  name,
  description,
  onNameChange,
  onDescriptionChange,
  errors,
}: {
  name: string;
  description: string;
  onNameChange: (v: string) => void;
  onDescriptionChange: (v: string) => void;
  errors: { name?: string; description?: string };
}) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-nb-text">Identidade do agente</h2>
        <p className="text-sm text-nb-muted mt-1">
          Dê um nome e objetivo para o agente. Estas informações orientam as respostas.
        </p>
      </div>

      <div className="space-y-4">
        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-nb-secondary">
            Nome do agente <span className="text-nb-danger">*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            maxLength={100}
            placeholder="Ex: Agente de Suporte"
            className={baseInput}
            autoFocus
          />
          {errors.name && (
            <p className="text-xs text-nb-danger">{errors.name}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-nb-secondary">
            Objetivo do agente <span className="text-nb-danger">*</span>
          </label>
          <p className="text-xs text-nb-muted">
            Explique o que este agente deve fazer. Isso será usado para orientar as respostas.
          </p>
          <textarea
            value={description}
            onChange={(e) => onDescriptionChange(e.target.value)}
            rows={3}
            placeholder="Ex: Qualificar leads interessados nos serviços da empresa e responder dúvidas iniciais."
            className={baseInput}
          />
          {errors.description && (
            <p className="text-xs text-nb-danger">{errors.description}</p>
          )}
        </div>
      </div>
    </div>
  );
}
