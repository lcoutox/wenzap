"use client";

import type { OnboardingFormData } from "./OnboardingFlow";

type Props = {
  data: OnboardingFormData;
  onChange: (fields: Partial<OnboardingFormData>) => void;
  errors: Partial<Record<keyof OnboardingFormData, string>>;
};

const INDUSTRIES = [
  { value: "clinic_health", label: "Clínica / saúde" },
  { value: "real_estate", label: "Imobiliária" },
  { value: "automotive", label: "Concessionária / veículos" },
  { value: "ecommerce", label: "E-commerce" },
  { value: "professional_services", label: "Serviços profissionais" },
  { value: "education", label: "Educação" },
  { value: "saas_tech", label: "Tecnologia / SaaS" },
  { value: "retail", label: "Varejo" },
  { value: "other", label: "Outro" },
];

const ROLES = [
  { value: "owner_founder", label: "Dono / fundador" },
  { value: "partner_director", label: "Sócio / diretor" },
  { value: "sales_manager", label: "Gestor comercial" },
  { value: "support_manager", label: "Gestor de atendimento" },
  { value: "marketing", label: "Marketing" },
  { value: "sales", label: "Vendas" },
  { value: "operations", label: "Operação" },
  { value: "developer_it", label: "Desenvolvedor / TI" },
  { value: "other", label: "Outro" },
];

function SelectField({
  id,
  label,
  required,
  value,
  onChange,
  error,
  options,
  placeholder,
}: {
  id: string;
  label: string;
  required?: boolean;
  value: string;
  onChange: (v: string) => void;
  error?: string;
  options: { value: string; label: string }[];
  placeholder: string;
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-medium text-nb-secondary mb-1.5">
        {label} {required && <span className="text-nb-danger">*</span>}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`w-full bg-nb-elevated border rounded-xl px-3 py-2.5 text-sm transition-colors focus:outline-none focus:ring-1 focus:ring-nb-primary/30 cursor-pointer
          ${value ? "text-nb-text border-nb-border focus:border-nb-primary" : "text-nb-muted border-nb-border focus:border-nb-primary"}`}
      >
        <option value="" disabled>{placeholder}</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} className="bg-nb-elevated text-nb-text">
            {opt.label}
          </option>
        ))}
      </select>
      {error && <p role="alert" className="text-nb-danger text-xs mt-1">{error}</p>}
    </div>
  );
}

export function StepCompany({ data, onChange, errors }: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-nb-text">Conte um pouco sobre sua empresa</h2>
        <p className="text-nb-muted text-sm mt-1">
          Essas informações ajudam a entender seu contexto.
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <label htmlFor="company_name" className="block text-xs font-medium text-nb-secondary mb-1.5">
            Nome da empresa <span className="text-nb-danger">*</span>
          </label>
          <input
            id="company_name"
            type="text"
            value={data.company_name}
            onChange={(e) => onChange({ company_name: e.target.value })}
            placeholder="Acme Ltda"
            className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors"
          />
          {errors.company_name && (
            <p role="alert" className="text-nb-danger text-xs mt-1">{errors.company_name}</p>
          )}
        </div>

        <SelectField
          id="company_industry"
          label="Segmento / indústria"
          required
          value={data.company_industry}
          onChange={(v) => onChange({ company_industry: v })}
          error={errors.company_industry}
          options={INDUSTRIES}
          placeholder="Selecione um segmento"
        />

        <SelectField
          id="role"
          label="Cargo ou função"
          required
          value={data.role}
          onChange={(v) => onChange({ role: v })}
          error={errors.role}
          options={ROLES}
          placeholder="Selecione seu cargo"
        />

        <div>
          <label htmlFor="company_website" className="block text-xs font-medium text-nb-secondary mb-1.5">
            Site da empresa <span className="text-nb-muted font-normal">(opcional)</span>
          </label>
          <input
            id="company_website"
            type="url"
            value={data.company_website}
            onChange={(e) => onChange({ company_website: e.target.value })}
            placeholder="https://suaempresa.com.br"
            className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors"
          />
          {errors.company_website && (
            <p role="alert" className="text-nb-danger text-xs mt-1">{errors.company_website}</p>
          )}
        </div>
      </div>
    </div>
  );
}
