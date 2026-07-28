"use client";

import { Plus, Trash2 } from "lucide-react";

export type MetadataEntry = { key: string; value: string };

export function metadataToEntries(metadata: Record<string, unknown> | null | undefined): MetadataEntry[] {
  if (!metadata) return [];
  return Object.entries(metadata).map(([key, value]) => ({ key, value: String(value) }));
}

export function entriesToMetadata(entries: MetadataEntry[]): Record<string, string> {
  const result: Record<string, string> = {};
  for (const { key, value } of entries) {
    const trimmedKey = key.trim();
    if (trimmedKey) result[trimmedKey] = value;
  }
  return result;
}

const inputCls =
  "flex-1 px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary disabled:opacity-60";

export function CatalogMetadataEditor({
  entries,
  onChange,
  disabled,
}: {
  entries: MetadataEntry[];
  onChange: (entries: MetadataEntry[]) => void;
  disabled?: boolean;
}) {
  function updateEntry(index: number, field: "key" | "value", val: string) {
    onChange(entries.map((entry, i) => (i === index ? { ...entry, [field]: val } : entry)));
  }

  function removeEntry(index: number) {
    onChange(entries.filter((_, i) => i !== index));
  }

  function addEntry() {
    onChange([...entries, { key: "", value: "" }]);
  }

  return (
    <div className="flex flex-col gap-2">
      {entries.map((entry, i) => (
        <div key={i} className="flex items-center gap-2">
          <input
            disabled={disabled}
            value={entry.key}
            onChange={(e) => updateEntry(i, "key", e.target.value)}
            placeholder="Ex: estilo"
            className={inputCls}
          />
          <input
            disabled={disabled}
            value={entry.value}
            onChange={(e) => updateEntry(i, "value", e.target.value)}
            placeholder="Ex: fine line"
            className={inputCls}
          />
          {!disabled && (
            <button
              type="button"
              onClick={() => removeEntry(i)}
              className="p-2 rounded-xl text-nb-muted hover:text-nb-danger hover:bg-nb-elevated transition-colors flex-shrink-0"
              aria-label="Remover atributo"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      ))}
      {!disabled && (
        <button
          type="button"
          onClick={addEntry}
          className="flex items-center gap-1.5 text-xs font-medium text-nb-primary hover:text-nb-primary-strong transition-colors self-start"
        >
          <Plus className="w-3.5 h-3.5" />
          Adicionar atributo
        </button>
      )}
    </div>
  );
}
