"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api";
import { WenzapIcon } from "@/components/auth/WenzapIcon";
import { OnboardingProgress } from "./OnboardingProgress";
import { StepPersonal } from "./StepPersonal";
import { StepIntent } from "./StepIntent";
import { StepCompany } from "./StepCompany";
import { StepOrigin } from "./StepOrigin";

// ── Types ──────────────────────────────────────────────────────────────────────

export type OnboardingFormData = {
  full_name: string;
  phone: string;
  main_objective: string;
  expected_monthly_conversations: string;
  ai_experience: string;
  company_name: string;
  company_industry: string;
  company_website: string;
  role: string;
  heard_from: string;
  contact_consent: boolean;
};

type FieldErrors = Partial<Record<keyof OnboardingFormData, string>>;

const TOTAL_STEPS = 4;

const EMPTY_FORM: OnboardingFormData = {
  full_name: "",
  phone: "",
  main_objective: "",
  expected_monthly_conversations: "",
  ai_experience: "",
  company_name: "",
  company_industry: "",
  company_website: "",
  role: "",
  heard_from: "",
  contact_consent: false,
};

// ── Validation ─────────────────────────────────────────────────────────────────

function validateStep(step: number, data: OnboardingFormData): FieldErrors {
  const errors: FieldErrors = {};
  const t = (s: string) => s.trim();

  if (step === 1) {
    if (!t(data.full_name)) {
      errors.full_name = "Informe seu nome completo.";
    } else if (t(data.full_name).length < 2) {
      errors.full_name = "O nome deve ter pelo menos 2 caracteres.";
    }
    if (!data.phone) {
      errors.phone = "Informe um telefone válido.";
    } else {
      // phone is stored as E.164, e.g. "+5537999999999"
      const allDigits = data.phone.replace(/\D/g, ""); // total digits incl. country code
      const isBR = data.phone.startsWith("+55");
      const nationalDigits = isBR ? allDigits.slice(2) : allDigits.slice(1); // rough: drop leading country code
      const valid = isBR
        ? nationalDigits.length >= 10 && nationalDigits.length <= 11
        : allDigits.length >= 7 && allDigits.length <= 15;
      if (!valid) errors.phone = "Informe um telefone válido.";
    }
  }

  if (step === 2) {
    if (!data.main_objective) errors.main_objective = "Selecione uma opção.";
    if (!data.expected_monthly_conversations) errors.expected_monthly_conversations = "Selecione uma opção.";
    if (!data.ai_experience) errors.ai_experience = "Selecione uma opção.";
  }

  if (step === 3) {
    if (!t(data.company_name)) {
      errors.company_name = "Informe o nome da empresa.";
    } else if (t(data.company_name).length < 2) {
      errors.company_name = "O nome deve ter pelo menos 2 caracteres.";
    }
    if (!data.company_industry) errors.company_industry = "Selecione um segmento.";
    if (!data.role) errors.role = "Selecione uma opção.";
    if (data.company_website.trim()) {
      const url = data.company_website.trim();
      if (!url.startsWith("http://") && !url.startsWith("https://")) {
        errors.company_website = "O site deve começar com http:// ou https://";
      }
    }
  }

  if (step === 4) {
    if (!data.heard_from) errors.heard_from = "Selecione uma opção.";
  }

  return errors;
}

// ── Component ──────────────────────────────────────────────────────────────────

export function OnboardingFlow() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [data, setData] = useState<OnboardingFormData>(EMPTY_FORM);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [globalError, setGlobalError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function handleChange(fields: Partial<OnboardingFormData>) {
    setData((prev) => ({ ...prev, ...fields }));
    // Clear errors for fields being edited.
    const cleared: FieldErrors = {};
    for (const key of Object.keys(fields) as (keyof OnboardingFormData)[]) {
      cleared[key] = undefined;
    }
    setErrors((prev) => ({ ...prev, ...cleared }));
  }

  function handleNext() {
    const stepErrors = validateStep(step, data);
    if (Object.keys(stepErrors).length > 0) {
      setErrors(stepErrors);
      return;
    }
    setErrors({});
    setStep((s) => s + 1);
  }

  function handleBack() {
    setErrors({});
    setGlobalError("");
    setStep((s) => s - 1);
  }

  async function handleSubmit() {
    const stepErrors = validateStep(4, data);
    if (Object.keys(stepErrors).length > 0) {
      setErrors(stepErrors);
      return;
    }

    setSubmitting(true);
    setGlobalError("");

    try {
      await api.onboarding.submit({
        full_name: data.full_name.trim(),
        phone: data.phone.trim(),
        main_objective: data.main_objective,
        expected_monthly_conversations: data.expected_monthly_conversations,
        ai_experience: data.ai_experience,
        company_name: data.company_name.trim(),
        company_industry: data.company_industry,
        company_website: data.company_website.trim() || null,
        role: data.role,
        heard_from: data.heard_from,
        contact_consent: data.contact_consent,
      });

      // Decide redirect: no agents → create first; otherwise → dashboard.
      try {
        const agents = await api.agents.list();
        router.push(agents.length === 0 ? "/dashboard/agents/new" : "/dashboard");
      } catch {
        router.push("/dashboard");
      }
    } catch {
      setGlobalError("Não foi possível salvar seu onboarding. Tente novamente.");
      setSubmitting(false);
    }
  }

  const isLastStep = step === TOTAL_STEPS;

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 py-12">
      {/* Logo */}
      <div className="flex items-center gap-2.5 mb-10">
        <WenzapIcon size={28} />
        <span className="text-nb-text font-bold text-lg tracking-tight">Wenzap</span>
      </div>

      {/* Card */}
      <div className="w-full max-w-lg">
        {/* Header copy */}
        <div className="mb-6 text-center">
          <p className="text-nb-muted text-sm">
            Com algumas respostas rápidas, vamos adaptar sua experiência no Wenzap.
          </p>
        </div>

        {/* Progress */}
        <div className="mb-8">
          <OnboardingProgress current={step} total={TOTAL_STEPS} />
        </div>

        {/* Step content */}
        <div className="bg-nb-panel border border-nb-border rounded-2xl p-6 sm:p-8">
          {step === 1 && (
            <StepPersonal data={data} onChange={handleChange} errors={errors} />
          )}
          {step === 2 && (
            <StepIntent data={data} onChange={handleChange} errors={errors} />
          )}
          {step === 3 && (
            <StepCompany data={data} onChange={handleChange} errors={errors} />
          )}
          {step === 4 && (
            <StepOrigin data={data} onChange={handleChange} errors={errors} />
          )}

          {/* Global error */}
          {globalError && (
            <p role="alert" aria-live="polite" className="mt-4 text-nb-danger text-sm text-center">
              {globalError}
            </p>
          )}

          {/* Navigation */}
          <div className="flex items-center justify-between mt-8 pt-6 border-t border-nb-border">
            <button
              type="button"
              onClick={handleBack}
              disabled={step === 1 || submitting}
              className="px-4 py-2 text-sm text-nb-secondary hover:text-nb-text transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
            >
              ← Voltar
            </button>

            {isLastStep ? (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={submitting}
                className="px-6 py-2.5 rounded-xl bg-nb-primary text-nb-bg text-sm font-semibold hover:opacity-90 disabled:opacity-50 transition-opacity cursor-pointer"
              >
                {submitting ? "Salvando..." : "Começar →"}
              </button>
            ) : (
              <button
                type="button"
                onClick={handleNext}
                className="px-6 py-2.5 rounded-xl bg-nb-primary text-nb-bg text-sm font-semibold hover:opacity-90 transition-opacity cursor-pointer"
              >
                Continuar →
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
