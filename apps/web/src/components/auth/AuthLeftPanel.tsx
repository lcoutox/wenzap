import { WenzapIcon } from "./WenzapIcon";

const features = [
  "Agentes de IA para atendimento, vendas e operações",
  "Workspaces seguros e multi-tenant",
  "Base preparada para integrações e automações",
];

export function AuthLeftPanel() {
  return (
    <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 bg-nb-surface border-r border-nb-border">
      <div className="flex items-center gap-2.5">
        <WenzapIcon size={32} />
        <span className="text-nb-text font-bold text-lg tracking-tight">Wenzap</span>
      </div>

      <div className="space-y-8">
        <div className="space-y-4">
          <h1 className="text-4xl font-bold text-nb-text leading-tight">
            Orquestre agentes de IA para seu negócio
          </h1>
          <p className="text-nb-secondary text-lg leading-relaxed">
            Crie e gerencie agentes de IA conectados aos dados, canais e processos da sua empresa.
          </p>
        </div>

        <ul className="space-y-4">
          {features.map((feature) => (
            <li key={feature} className="flex items-start gap-3">
              <div className="mt-1 w-4 h-4 rounded-full bg-nb-primary-bg border border-nb-primary/40 flex items-center justify-center flex-shrink-0">
                <div className="w-1.5 h-1.5 rounded-full bg-nb-primary" />
              </div>
              <span className="text-nb-secondary text-sm">{feature}</span>
            </li>
          ))}
        </ul>
      </div>

      <p className="text-nb-muted text-xs">
        © {new Date().getFullYear()} Wenzap. Todos os direitos reservados.
      </p>
    </div>
  );
}
