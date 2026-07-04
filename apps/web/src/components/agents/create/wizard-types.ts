import type { GuidedConfig } from "@/lib/api";
import type { TemplateId } from "./templates";

export type CreativityLevel = "precise" | "balanced" | "creative";

export interface WizardState {
  // Step 1
  templateId: TemplateId | null;
  guidedConfig: GuidedConfig;
  // Step 2
  name: string;
  description: string;
  // Step 3
  selectedKbIds: string[];
  // Step 4
  aiModelId: string | null;
  creativity: CreativityLevel;
}

export const EMPTY_GUIDED_CONFIG: GuidedConfig = {
  role: null,
  main_objective: null,
  posture: null,
  initiative: null,
  when_no_info: null,
  do_items: [],
  custom_should_do: [],
  dont_items: [],
  custom_should_not_do: [],
  extra_restrictions: null,
  good_response_example: null,
  bad_response_example: null,
};

export const INITIAL_WIZARD_STATE: WizardState = {
  templateId: null,
  guidedConfig: EMPTY_GUIDED_CONFIG,
  name: "",
  description: "",
  selectedKbIds: [],
  aiModelId: null,
  creativity: "balanced",
};

export const CREATIVITY_TEMPERATURE: Record<CreativityLevel, number> = {
  precise: 0.2,
  balanced: 0.7,
  creative: 0.9,
};
