import type { WizardState } from "./wizard-types";
import { ALL_RULES } from "./wizard-types";

export function buildPersona(tones: string[]): string {
  if (tones.length === 0) return "";
  return tones.join(", ") + ".";
}

export function buildSystemPrompt(state: WizardState): string {
  const lines: string[] = [];

  lines.push(`Você é ${state.name || "um agente de IA"}.`);
  lines.push("");

  if (state.description.trim()) {
    lines.push("Objetivo:");
    lines.push(state.description.trim());
    lines.push("");
  }

  if (state.tones.length > 0) {
    lines.push("Tom de voz:");
    lines.push(state.tones.join(", ") + ".");
    lines.push("");
  }

  if (state.rules.length > 0) {
    const ruleLabels = state.rules
      .map((id) => ALL_RULES.find((r) => r.id === id)?.label)
      .filter(Boolean) as string[];
    if (ruleLabels.length > 0) {
      lines.push("Regras de atendimento:");
      ruleLabels.forEach((label) => lines.push(`- ${label}.`));
      lines.push("");
    }
  }

  if (state.avoidText.trim()) {
    lines.push("O que evitar:");
    lines.push(state.avoidText.trim());
    lines.push("");
  }

  if (state.additionalInstructions.trim()) {
    lines.push("Instruções adicionais:");
    lines.push(state.additionalInstructions.trim());
    lines.push("");
  }

  lines.push("Quando não souber responder:");
  lines.push(
    "Informe que não tem essa informação com segurança e oriente o cliente a falar com a equipe."
  );

  return lines.join("\n");
}
