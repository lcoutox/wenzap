import { SignIn } from "@clerk/nextjs";

const features = [
  "Agentes de IA para atendimento, vendas e operações",
  "Workspaces seguros e multi-tenant",
  "Base preparada para integrações e automações",
];

export default function SignInPage() {
  return (
    <div className="min-h-screen flex bg-gray-950">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 bg-gray-900 border-r border-gray-800">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
              <span className="text-white font-bold text-sm">N</span>
            </div>
            <span className="text-white font-bold text-lg tracking-tight">Nexbrain</span>
          </div>
        </div>

        <div className="space-y-8">
          <div className="space-y-4">
            <h1 className="text-4xl font-bold text-white leading-tight">
              Orquestre agentes de IA para seu negócio
            </h1>
            <p className="text-gray-400 text-lg leading-relaxed">
              Crie e gerencie agentes de IA conectados aos dados, canais e processos da sua empresa.
            </p>
          </div>

          <ul className="space-y-4">
            {features.map((feature) => (
              <li key={feature} className="flex items-start gap-3">
                <div className="mt-1 w-4 h-4 rounded-full bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center flex-shrink-0">
                  <div className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                </div>
                <span className="text-gray-300 text-sm">{feature}</span>
              </li>
            ))}
          </ul>
        </div>

        <p className="text-gray-600 text-xs">
          © {new Date().getFullYear()} Nexbrain. Todos os direitos reservados.
        </p>
      </div>

      {/* Right panel — Clerk sign-in */}
      <div className="flex-1 flex flex-col items-center justify-center p-8">
        {/* Mobile logo */}
        <div className="flex lg:hidden items-center gap-2 mb-8">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">N</span>
          </div>
          <span className="text-white font-bold text-lg tracking-tight">Nexbrain</span>
        </div>

        <div className="w-full max-w-sm space-y-6">
          <div className="text-center lg:text-left space-y-1">
            <h2 className="text-2xl font-bold text-white">Entre no Nexbrain</h2>
            <p className="text-gray-400 text-sm">
              Acesse sua conta para continuar.
            </p>
          </div>

          <SignIn
            appearance={{
              variables: {
                colorPrimary: "#4f46e5",
                colorBackground: "#111827",
                colorInputBackground: "#1f2937",
                colorInputText: "#f9fafb",
                colorText: "#f9fafb",
                colorTextSecondary: "#9ca3af",
                colorNeutral: "#374151",
                borderRadius: "0.5rem",
                fontFamily: "inherit",
              },
              elements: {
                card: "bg-gray-900 border border-gray-800 shadow-xl",
                headerTitle: "hidden",
                headerSubtitle: "hidden",
                socialButtonsBlockButton:
                  "bg-gray-800 border border-gray-700 text-gray-200 hover:bg-gray-700 transition-colors",
                dividerLine: "bg-gray-700",
                dividerText: "text-gray-500",
                formFieldInput:
                  "bg-gray-800 border-gray-700 text-gray-100 placeholder:text-gray-500 focus:border-indigo-500 focus:ring-indigo-500",
                formFieldLabel: "text-gray-300",
                formButtonPrimary:
                  "bg-indigo-600 hover:bg-indigo-500 text-white transition-colors",
                footerActionLink: "text-indigo-400 hover:text-indigo-300",
                identityPreviewText: "text-gray-300",
                identityPreviewEditButton: "text-indigo-400",
                formResendCodeLink: "text-indigo-400",
                otpCodeFieldInput:
                  "bg-gray-800 border-gray-700 text-gray-100",
              },
            }}
          />
        </div>
      </div>
    </div>
  );
}
