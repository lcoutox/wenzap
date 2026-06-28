const STEPS = [
  "Tipo",
  "Identidade",
  "Comportamento",
  "Conhecimento",
  "Modelo",
  "Revisão",
];

export function WizardProgress({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-0">
      {STEPS.map((label, i) => {
        const step = i + 1;
        const done    = step < current;
        const active  = step === current;
        const future  = step > current;
        return (
          <div key={step} className="flex items-center">
            {/* Connector left */}
            {i > 0 && (
              <div
                className={`h-px w-6 sm:w-10 transition-colors ${
                  done ? "bg-nb-primary" : "bg-nb-border"
                }`}
              />
            )}
            <div className="flex flex-col items-center gap-1">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                  done
                    ? "bg-nb-primary text-white"
                    : active
                    ? "bg-nb-primary text-white ring-4 ring-nb-primary/20"
                    : "bg-nb-elevated border border-nb-border text-nb-muted"
                }`}
              >
                {done ? (
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  step
                )}
              </div>
              <span
                className={`text-[10px] font-medium hidden sm:block ${
                  active ? "text-nb-primary-strong" : future ? "text-nb-muted" : "text-nb-muted"
                }`}
              >
                {label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
