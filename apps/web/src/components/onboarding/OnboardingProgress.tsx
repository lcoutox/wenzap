"use client";

type Props = {
  current: number;
  total: number;
};

export function OnboardingProgress({ current, total }: Props) {
  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-nb-muted font-medium">
          Etapa {current} de {total}
        </span>
        <span className="text-xs text-nb-muted">
          {Math.round((current / total) * 100)}%
        </span>
      </div>
      <div className="h-1 w-full bg-nb-elevated rounded-full overflow-hidden">
        <div
          className="h-full bg-nb-primary rounded-full transition-all duration-500 ease-out"
          style={{ width: `${(current / total) * 100}%` }}
        />
      </div>
    </div>
  );
}
