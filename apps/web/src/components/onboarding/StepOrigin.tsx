"use client";

import type { OnboardingFormData } from "./OnboardingFlow";

type Props = {
  data: OnboardingFormData;
  onChange: (fields: Partial<OnboardingFormData>) => void;
  errors: Partial<Record<keyof OnboardingFormData, string>>;
};

const HEARD_FROM_OPTIONS = [
  { value: "google", label: "Google" },
  { value: "instagram", label: "Instagram" },
  { value: "youtube", label: "YouTube" },
  { value: "referral", label: "Indicação" },
  { value: "chatgpt", label: "ChatGPT" },
  { value: "community", label: "Comunidade" },
  { value: "other", label: "Outro" },
];

export function StepOrigin({ data, onChange, errors }: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-nb-text">Quase lá</h2>
        <p className="text-nb-muted text-sm mt-1">
          Só precisamos saber como você chegou até aqui.
        </p>
      </div>

      <div className="space-y-6">
        {/* heard_from */}
        <div>
          <p className="text-xs font-medium text-nb-secondary mb-2">
            Onde conheceu o Wenzap? <span className="text-nb-danger">*</span>
          </p>
          <div className="flex flex-wrap gap-2">
            {HEARD_FROM_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => onChange({ heard_from: opt.value })}
                aria-pressed={data.heard_from === opt.value}
                className={`px-3 py-2 rounded-xl text-sm font-medium border transition-colors cursor-pointer
                  ${data.heard_from === opt.value
                    ? "bg-nb-primary-bg border-nb-primary text-nb-primary"
                    : "bg-nb-elevated border-nb-border text-nb-secondary hover:border-nb-border-strong hover:text-nb-text"
                  }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          {errors.heard_from && (
            <p role="alert" className="text-nb-danger text-xs mt-1">{errors.heard_from}</p>
          )}
        </div>

        {/* contact_consent */}
        <div>
          <label className="flex items-start gap-3 cursor-pointer group">
            <div className="relative mt-0.5 flex-shrink-0">
              <input
                id="contact_consent"
                type="checkbox"
                checked={data.contact_consent}
                onChange={(e) => onChange({ contact_consent: e.target.checked })}
                className="sr-only peer"
              />
              <div
                className={`w-5 h-5 rounded-md border-2 transition-colors
                  ${data.contact_consent
                    ? "bg-nb-primary border-nb-primary"
                    : "bg-nb-elevated border-nb-border group-hover:border-nb-border-strong"
                  }`}
              >
                {data.contact_consent && (
                  <svg className="w-3 h-3 text-nb-bg absolute top-0.5 left-0.5" viewBox="0 0 12 12" fill="none">
                    <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </div>
            </div>
            <span className="text-sm text-nb-secondary leading-snug">
              Autorizo o time do Wenzap a entrar em contato para entender melhor minhas necessidades.
            </span>
          </label>
        </div>
      </div>
    </div>
  );
}
