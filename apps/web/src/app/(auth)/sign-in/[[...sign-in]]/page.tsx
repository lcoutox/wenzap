import { SignIn } from "@clerk/nextjs";

const features = [
  "Agentes de IA para atendimento, vendas e operações",
  "Workspaces seguros e multi-tenant",
  "Base preparada para integrações e automações",
];

function WenzapIcon({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 270 270" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M 18,32 6,53 1,71 l -1,82 4,20 9,18 15,17 15,10 -5,26 1,7 4,5 4,2 h 9 l 60,-31 h 81 l 13,-3 24,-12 18,-18 8,-14 6,-19 1,-85 L 264,60 257,43 248,30 232,15 216,6 193,0 H 75 L 57,4 40,12 28,21 Z m 19,13 9,-9 9,-6 12,-5 10,-2 h 114 l 16,4 11,6 12,11 7,10 7,23 v 76 l -4,15 -8,14 -14,13 -17,8 -12,2 h -79 l -45,22 -1,-5 2,-7 V 204 L 46,193 36,183 27,168 24,158 23,81 27,62 Z"
        fill="#00E09A" fillRule="evenodd"
      />
      <path
        d="m 62,76 -2,4 v 6 l 27,73 9,6 h 11 l 8,-5 12,-31 6,-11 3,1 16,41 8,5 h 12 l 4,-2 7,-10 24,-67 -1,-8 -5,-5 -10,-1 -4,2 -4,6 -15,46 -2,3 h -2 l -18,-47 -8,-6 -11,1 -7,7 -15,43 -4,1 -17,-48 -3,-5 -5,-3 h -8 z"
        fill="#00E09A" fillRule="evenodd"
      />
    </svg>
  );
}

export default function SignInPage() {
  return (
    <div className="min-h-screen flex bg-nb-bg">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 bg-nb-surface border-r border-nb-border">
        <div>
          <div className="flex items-center gap-2.5">
            <WenzapIcon size={32} />
            <span className="text-nb-text font-bold text-lg tracking-tight">Wenzap</span>
          </div>
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

      {/* Right panel — Clerk sign-in */}
      <div className="flex-1 flex flex-col items-center justify-center p-8">
        {/* Mobile logo */}
        <div className="flex lg:hidden items-center gap-2.5 mb-8">
          <WenzapIcon size={28} />
          <span className="text-nb-text font-bold text-lg tracking-tight">Wenzap</span>
        </div>

        <div className="w-full max-w-sm space-y-6">
          <div className="text-center lg:text-left space-y-1">
            <h2 className="text-2xl font-bold text-nb-text">Entre no Wenzap</h2>
            <p className="text-nb-muted text-sm">
              Acesse sua conta para continuar.
            </p>
          </div>

          <SignIn
            appearance={{
              variables: {
                colorPrimary: "#00E09A",
                colorBackground: "#111827",
                colorInputBackground: "#1A2030",
                colorInputText: "#F9FAFB",
                colorText: "#F9FAFB",
                colorTextSecondary: "#9CA3AF",
                colorNeutral: "#374151",
                borderRadius: "0.5rem",
                fontFamily: "inherit",
              },
              elements: {
                card: "bg-nb-panel border border-nb-border shadow-xl",
                headerTitle: "hidden",
                headerSubtitle: "hidden",
                socialButtonsBlockButton:
                  "bg-nb-elevated border border-nb-border text-nb-secondary hover:bg-nb-soft transition-colors",
                dividerLine: "bg-nb-border",
                dividerText: "text-nb-muted",
                formFieldInput:
                  "bg-nb-elevated border-nb-border text-nb-text placeholder:text-nb-muted focus:border-nb-primary focus:ring-nb-primary",
                formFieldLabel: "text-nb-secondary",
                formButtonPrimary:
                  "bg-nb-primary hover:opacity-90 text-nb-bg font-semibold transition-colors",
                footerActionLink: "text-nb-primary hover:text-nb-primary-strong",
                identityPreviewText: "text-nb-secondary",
                identityPreviewEditButton: "text-nb-primary",
                formResendCodeLink: "text-nb-primary",
                otpCodeFieldInput: "bg-nb-elevated border-nb-border text-nb-text",
              },
            }}
          />
        </div>
      </div>
    </div>
  );
}
