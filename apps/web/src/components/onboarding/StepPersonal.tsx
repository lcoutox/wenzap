"use client";

import type { OnboardingFormData } from "./OnboardingFlow";

type Props = {
  data: OnboardingFormData;
  onChange: (fields: Partial<OnboardingFormData>) => void;
  errors: Partial<Record<keyof OnboardingFormData, string>>;
};

export function StepPersonal({ data, onChange, errors }: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-nb-text">Vamos começar por você</h2>
        <p className="text-nb-muted text-sm mt-1">
          Informe seus dados para personalizar sua experiência.
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <label htmlFor="full_name" className="block text-xs font-medium text-nb-secondary mb-1.5">
            Nome completo <span className="text-nb-danger">*</span>
          </label>
          <input
            id="full_name"
            type="text"
            autoComplete="name"
            value={data.full_name}
            onChange={(e) => onChange({ full_name: e.target.value })}
            placeholder="Seu nome completo"
            className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors"
          />
          {errors.full_name && (
            <p role="alert" className="text-nb-danger text-xs mt-1">{errors.full_name}</p>
          )}
        </div>

        <div>
          <label htmlFor="phone" className="block text-xs font-medium text-nb-secondary mb-1.5">
            Telefone / WhatsApp <span className="text-nb-danger">*</span>
          </label>
          <input
            id="phone"
            type="tel"
            autoComplete="tel"
            value={data.phone}
            onChange={(e) => onChange({ phone: e.target.value })}
            placeholder="55 11 9 8888-7777"
            className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors"
          />
          {errors.phone && (
            <p role="alert" className="text-nb-danger text-xs mt-1">{errors.phone}</p>
          )}
        </div>
      </div>
    </div>
  );
}
