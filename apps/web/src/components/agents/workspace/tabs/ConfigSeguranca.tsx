type SecurityItem = {
  label: string;
  description: string;
};

const ITEMS: SecurityItem[] = [
  {
    label: "Acesso público",
    description: "Permite que o agente seja acessado sem autenticação via widget ou link público.",
  },
  {
    label: "Incluir fontes nas respostas",
    description: "Mostra ao usuário as fontes da base de conhecimento usadas para gerar a resposta.",
  },
  {
    label: "Restringir a domínios permitidos",
    description: "Limita o widget a apenas funcionar em domínios específicos cadastrados.",
  },
  {
    label: "Limite de uso por sessão",
    description: "Restringe o número de mensagens por conversa para evitar abuso.",
  },
  {
    label: "Moderação de conteúdo",
    description: "Bloqueia automaticamente mensagens inadequadas ou fora do escopo.",
  },
  {
    label: "Registrar feedback negativo",
    description: "Coleta feedback do usuário quando a resposta não foi útil.",
  },
];

export function ConfigSeguranca() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-nb-text">Segurança e acesso</h2>
        <p className="text-sm text-nb-muted mt-1">
          Controles de privacidade, moderação e limites de uso. Disponíveis na Phase 5.
        </p>
      </div>

      <div className="bg-nb-panel rounded-2xl border border-nb-border divide-y divide-nb-border">
        {ITEMS.map(({ label, description }) => (
          <div key={label} className="flex items-center justify-between gap-4 px-5 py-4">
            <div className="min-w-0">
              <p className="text-sm font-medium text-nb-secondary">{label}</p>
              <p className="text-xs text-nb-muted mt-0.5">{description}</p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded bg-nb-elevated text-nb-muted border border-nb-border leading-none">
                EM BREVE
              </span>
              <div className="w-9 h-5 rounded-full bg-nb-border opacity-50 cursor-not-allowed" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
