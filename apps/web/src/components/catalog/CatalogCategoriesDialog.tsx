"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Pencil, Plus, X } from "lucide-react";
import { api } from "@/lib/api";
import type { CatalogCategory } from "@/lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
  onCategoriesChange?: (categories: CatalogCategory[]) => void;
}

interface RowProps {
  cat: CatalogCategory;
  onSaved: (cat: CatalogCategory) => void;
}

function CategoryRow({ cat, onSaved }: RowProps) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(cat.name);
  const [description, setDescription] = useState(cat.description ?? "");
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const save = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const updated = await api.catalog.categories.update(cat.id, {
        name: name.trim(),
        description: description.trim() || undefined,
      });
      onSaved(updated);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const toggle = async () => {
    setSaving(true);
    try {
      const updated = await api.catalog.categories.update(cat.id, {
        is_active: !cat.is_active,
      });
      onSaved(updated);
    } finally {
      setSaving(false);
    }
  };

  if (editing) {
    return (
      <div className="flex flex-col gap-2 p-3 rounded-xl border border-nb-primary bg-nb-primary/5">
        <input
          ref={inputRef}
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }}
          className="px-3 py-1.5 rounded-lg bg-nb-base border border-nb-border text-sm text-nb-text focus:outline-none focus:ring-1 focus:ring-nb-primary"
          placeholder="Nome da categoria"
        />
        <input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }}
          className="px-3 py-1.5 rounded-lg bg-nb-base border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary"
          placeholder="Descrição (opcional)"
        />
        <div className="flex gap-2 justify-end">
          <button
            onClick={() => setEditing(false)}
            className="px-3 py-1 rounded-lg border border-nb-border text-xs text-nb-muted hover:bg-nb-elevated transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={save}
            disabled={saving || !name.trim()}
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-nb-primary text-white text-xs font-medium hover:bg-nb-primary-strong transition-colors disabled:opacity-50"
          >
            <Check className="w-3 h-3" />
            Salvar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-3 px-3 py-2.5 rounded-xl border ${cat.is_active ? "border-nb-border bg-nb-elevated" : "border-nb-border bg-nb-base opacity-60"}`}>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-nb-text truncate">{cat.name}</p>
        {cat.description && (
          <p className="text-xs text-nb-muted truncate">{cat.description}</p>
        )}
      </div>
      <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${cat.is_active ? "bg-nb-success/10 text-nb-success border-nb-success/20" : "bg-nb-elevated text-nb-muted border-nb-border"}`}>
        {cat.is_active ? "Ativa" : "Inativa"}
      </span>
      <button
        onClick={() => setEditing(true)}
        title="Editar"
        className="p-1.5 rounded-lg hover:bg-nb-border transition-colors text-nb-muted hover:text-nb-text"
      >
        <Pencil className="w-3.5 h-3.5" />
      </button>
      <button
        onClick={toggle}
        disabled={saving}
        title={cat.is_active ? "Desativar" : "Ativar"}
        className="text-xs px-2 py-1 rounded-lg border border-nb-border hover:bg-nb-border transition-colors text-nb-muted disabled:opacity-50"
      >
        {cat.is_active ? "Desativar" : "Ativar"}
      </button>
    </div>
  );
}

export function CatalogCategoriesDialog({ open, onClose, onCategoriesChange }: Props) {
  const [categories, setCategories] = useState<CatalogCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setLoading(true);
    api.catalog.categories.list(true)
      .then((cats) => setCategories(cats))
      .catch(() => setError("Erro ao carregar categorias."))
      .finally(() => setLoading(false));
  }, [open]);

  const notify = (cats: CatalogCategory[]) => {
    setCategories(cats);
    onCategoriesChange?.(cats.filter((c) => c.is_active));
  };

  const handleRowSaved = (updated: CatalogCategory) => {
    const next = categories.map((c) => (c.id === updated.id ? updated : c));
    notify(next);
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const created = await api.catalog.categories.create({
        name: newName.trim(),
        description: newDesc.trim() || undefined,
      });
      const next = [...categories, created];
      notify(next);
      setNewName("");
      setNewDesc("");
    } catch {
      setError("Erro ao criar categoria.");
    } finally {
      setCreating(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-nb-panel rounded-2xl border border-nb-border shadow-xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-nb-border shrink-0">
          <div>
            <h2 className="text-base font-bold text-nb-text">Categorias do Catálogo</h2>
            <p className="mt-1 text-xs text-nb-muted max-w-sm">
              Organize seus itens em categorias para facilitar a gestão e ajudar os agentes a entenderem melhor o que sua empresa oferece.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-nb-elevated transition-colors text-nb-muted hover:text-nb-text ml-3 shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-2 min-h-0">
          {loading ? (
            <div className="flex flex-col gap-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-12 rounded-xl bg-nb-elevated animate-pulse" />
              ))}
            </div>
          ) : error ? (
            <p className="text-sm text-nb-danger">{error}</p>
          ) : categories.length === 0 ? (
            <p className="text-sm text-nb-muted text-center py-6">Nenhuma categoria criada ainda.</p>
          ) : (
            categories.map((cat) => (
              <CategoryRow key={cat.id} cat={cat} onSaved={handleRowSaved} />
            ))
          )}
        </div>

        {/* Create form */}
        <div className="p-5 border-t border-nb-border shrink-0 flex flex-col gap-3">
          <p className="text-xs font-semibold text-nb-text">Nova categoria</p>
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleCreate(); }}
            placeholder="Nome da categoria"
            className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary"
          />
          <input
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleCreate(); }}
            placeholder="Descrição (opcional)"
            className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary"
          />
          <button
            onClick={handleCreate}
            disabled={creating || !newName.trim()}
            className="flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-nb-primary text-white text-sm font-medium hover:bg-nb-primary-strong transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {creating ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <Plus className="w-4 h-4" />
            )}
            Criar categoria
          </button>
        </div>
      </div>
    </div>
  );
}
