"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  FileText,
  ImageIcon,
  Loader2,
  Star,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type {
  CatalogCategory,
  CatalogItem,
  CatalogItemStatus,
  CatalogMedia,
  MemberRole,
} from "@/lib/api";

const STATUS_OPTIONS: { value: CatalogItemStatus; label: string }[] = [
  { value: "active",      label: "Ativo"        },
  { value: "draft",       label: "Rascunho"     },
  { value: "inactive",    label: "Inativo"      },
  { value: "unavailable", label: "Indisponível" },
];

// ── Media section ──────────────────────────────────────────────────────────────

function MediaGallery({
  itemId,
  canWrite,
}: {
  itemId: string;
  canWrite: boolean;
}) {
  const [mediaList, setMediaList]   = useState<CatalogMedia[]>([]);
  const [loading, setLoading]       = useState(true);
  const [uploading, setUploading]   = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const fileRef                     = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.catalog.media
      .list(itemId)
      .then(setMediaList)
      .catch(() => {}) // storage may be unconfigured in dev
      .finally(() => setLoading(false));
  }, [itemId]);

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of Array.from(files)) {
        const fd = new FormData();
        fd.append("file", file);
        const media = await api.catalog.media.upload(itemId, fd);
        setMediaList((prev) => [...prev, media]);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro no upload");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function handleSetPrimary(mediaId: string) {
    try {
      const updated = await api.catalog.media.setPrimary(itemId, mediaId);
      setMediaList((prev) =>
        prev.map((m) => ({ ...m, is_primary: m.id === updated.id })),
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao definir primária");
    }
  }

  async function handleDelete(mediaId: string) {
    try {
      await api.catalog.media.delete(itemId, mediaId);
      setMediaList((prev) => {
        const remaining = prev.filter((m) => m.id !== mediaId);
        // If deleted was primary, promote first image
        const wasImg = prev.find((m) => m.id === mediaId);
        if (wasImg?.is_primary) {
          const nextImg = remaining.find((m) => m.file_type === "image");
          if (nextImg) nextImg.is_primary = true;
        }
        return remaining;
      });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao remover mídia");
    }
  }

  const sorted = [...mediaList].sort((a, b) => {
    if (a.is_primary !== b.is_primary) return a.is_primary ? -1 : 1;
    return a.sort_order - b.sort_order;
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-nb-text">Mídias</h2>
          <p className="text-xs text-nb-muted mt-0.5">
            Adicione imagens e documentos que seus agentes poderão usar durante o atendimento.
          </p>
        </div>
        {canWrite && (
          <label className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-xs font-medium text-nb-text hover:bg-nb-panel cursor-pointer transition-colors">
            {uploading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Upload className="w-3.5 h-3.5" />
            )}
            {uploading ? "Enviando…" : "Adicionar"}
            <input
              ref={fileRef}
              type="file"
              multiple
              accept="image/jpeg,image/png,image/webp,image/gif,application/pdf"
              className="sr-only"
              onChange={(e) => handleUpload(e.target.files)}
              disabled={uploading}
            />
          </label>
        )}
      </div>

      {error && (
        <p className="text-xs text-nb-danger flex items-center gap-1">
          <X className="w-3 h-3" /> {error}
        </p>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-5 h-5 animate-spin text-nb-muted" />
        </div>
      ) : sorted.length === 0 ? (
        <div
          className="flex flex-col items-center justify-center py-8 gap-2 rounded-xl border-2 border-dashed border-nb-border cursor-pointer hover:border-nb-primary/50 transition-colors"
          onClick={() => canWrite && fileRef.current?.click()}
        >
          <ImageIcon className="w-8 h-8 text-nb-muted/40" />
          <p className="text-xs text-nb-muted">
            {canWrite ? "Clique para adicionar imagens ou PDFs" : "Nenhuma mídia adicionada"}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {sorted.map((media) => (
            <MediaCard
              key={media.id}
              media={media}
              canWrite={canWrite}
              onSetPrimary={() => handleSetPrimary(media.id)}
              onDelete={() => handleDelete(media.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function MediaCard({
  media,
  canWrite,
  onSetPrimary,
  onDelete,
}: {
  media: CatalogMedia;
  canWrite: boolean;
  onSetPrimary: () => void;
  onDelete: () => void;
}) {
  const isImage = media.file_type === "image";

  return (
    <div className="group relative rounded-xl border border-nb-border bg-nb-elevated overflow-hidden">
      {/* Preview */}
      {isImage && media.preview_url ? (
        <div className="relative w-full aspect-square">
          <Image
            src={media.preview_url}
            alt={media.alt_text ?? media.display_name ?? media.original_filename}
            fill
            className="object-cover"
            unoptimized
          />
        </div>
      ) : (
        <div className="w-full aspect-square flex flex-col items-center justify-center gap-1 bg-nb-panel">
          <FileText className="w-8 h-8 text-nb-muted" />
          <span className="text-xs text-nb-muted text-center px-2 truncate w-full text-center">
            {media.original_filename}
          </span>
        </div>
      )}

      {/* Primary badge */}
      {media.is_primary && (
        <div className="absolute top-1.5 left-1.5 bg-nb-warning/90 text-white rounded-full p-0.5">
          <Star className="w-2.5 h-2.5 fill-white" />
        </div>
      )}

      {/* Actions (visible on hover) */}
      {canWrite && (
        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-2 gap-1">
          {isImage && !media.is_primary && (
            <button
              onClick={onSetPrimary}
              title="Definir como principal"
              className="flex items-center gap-1 px-2 py-1 rounded-lg bg-nb-warning text-white text-xs font-medium hover:bg-amber-400 transition-colors"
            >
              <Star className="w-3 h-3" />
            </button>
          )}
          {media.download_url && (
            <a
              href={media.download_url}
              target="_blank"
              rel="noreferrer"
              className="px-2 py-1 rounded-lg bg-white/20 text-white text-xs hover:bg-white/30 transition-colors"
            >
              Abrir
            </a>
          )}
          <button
            onClick={onDelete}
            title="Remover"
            className="ml-auto p-1.5 rounded-lg bg-nb-danger/80 text-white hover:bg-nb-danger transition-colors"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Filename below for non-image */}
      {!isImage && (
        <div className="px-2 py-1.5 border-t border-nb-border">
          <p className="text-xs text-nb-muted truncate">
            {media.display_name ?? media.original_filename}
          </p>
          <p className="text-xs text-nb-muted/60">
            {(media.size_bytes / 1024).toFixed(0)} KB
          </p>
        </div>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function EditCatalogItemPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [item, setItem]             = useState<CatalogItem | null>(null);
  const [categories, setCategories] = useState<CatalogCategory[]>([]);
  const [role, setRole]             = useState<MemberRole | null>(null);
  const [loading, setLoading]       = useState(true);
  const [saving, setSaving]         = useState(false);
  const [archiving, setArchiving]   = useState(false);
  const [error, setError]           = useState<string | null>(null);

  const [name, setName]                   = useState("");
  const [categoryId, setCategoryId]       = useState("");
  const [shortDesc, setShortDesc]         = useState("");
  const [description, setDescription]     = useState("");
  const [price, setPrice]                 = useState("");
  const [currency, setCurrency]           = useState("BRL");
  const [status, setStatus]               = useState<CatalogItemStatus>("active");
  const [sku, setSku]                     = useState("");
  const [externalId, setExternalId]       = useState("");
  const [tags, setTags]                   = useState("");
  const [isFeatured, setIsFeatured]       = useState(false);
  const [stockQuantity, setStockQuantity] = useState("");

  useEffect(() => {
    Promise.all([
      api.me(),
      api.catalog.items.get(id),
      api.catalog.categories.list(),
    ])
      .then(([me, fetchedItem, fetchedCats]) => {
        setRole(me.role);
        setItem(fetchedItem);
        setCategories(fetchedCats);

        setName(fetchedItem.name);
        setCategoryId(fetchedItem.category_id ?? "");
        setShortDesc(fetchedItem.short_description ?? "");
        setDescription(fetchedItem.description ?? "");
        setPrice(fetchedItem.price != null ? String(fetchedItem.price) : "");
        setCurrency(fetchedItem.currency);
        setStatus(fetchedItem.status);
        setSku(fetchedItem.sku ?? "");
        setExternalId(fetchedItem.external_id ?? "");
        setTags(fetchedItem.tags.join(", "));
        setIsFeatured(fetchedItem.is_featured);
        setStockQuantity(fetchedItem.stock_quantity != null ? String(fetchedItem.stock_quantity) : "");
      })
      .catch(() => setError("Item não encontrado"))
      .finally(() => setLoading(false));
  }, [id]);

  const canWrite = role === "owner" || role === "admin" || role === "member";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await api.catalog.items.update(id, {
        name: name.trim(),
        category_id: categoryId || null,
        short_description: shortDesc.trim() || undefined,
        description: description.trim() || undefined,
        price: price ? parseFloat(price) : null,
        currency,
        status,
        sku: sku.trim() || undefined,
        external_id: externalId.trim() || undefined,
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
        is_featured: isFeatured,
        stock_quantity: stockQuantity ? parseInt(stockQuantity, 10) : null,
      });
      router.push("/dashboard/catalog");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao salvar");
      setSaving(false);
    }
  }

  async function handleArchive() {
    if (!confirm("Arquivar este item? Ele não aparecerá mais no catálogo.")) return;
    setArchiving(true);
    try {
      await api.catalog.items.archive(id);
      router.push("/dashboard/catalog");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao arquivar");
      setArchiving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 text-nb-muted animate-spin" />
      </div>
    );
  }

  if (!item) {
    return <p className="text-sm text-nb-danger">{error ?? "Item não encontrado"}</p>;
  }

  return (
    <div className="flex flex-col gap-8 max-w-2xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/catalog"
            className="p-2 rounded-xl hover:bg-nb-elevated transition-colors"
          >
            <ArrowLeft className="w-4 h-4 text-nb-muted" />
          </Link>
          <h1 className="text-xl font-bold text-nb-text truncate max-w-sm">{item.name}</h1>
        </div>
        {canWrite && (
          <button
            onClick={handleArchive}
            disabled={archiving}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-nb-danger/30 text-nb-danger text-xs hover:bg-nb-danger/10 disabled:opacity-50 transition-colors"
          >
            {archiving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
            Arquivar
          </button>
        )}
      </div>

      {/* Media section */}
      <div className="bg-nb-panel rounded-2xl border border-nb-border p-5">
        <MediaGallery itemId={id} canWrite={canWrite} />
      </div>

      {/* Item form */}
      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-nb-text">
            Nome <span className="text-nb-danger">*</span>
          </label>
          <input
            required
            disabled={!canWrite}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary disabled:opacity-60"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-nb-text">Categoria</label>
          <select
            disabled={!canWrite}
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text focus:outline-none focus:ring-1 focus:ring-nb-primary disabled:opacity-60"
          >
            <option value="">Sem categoria</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-nb-text">Descrição curta</label>
          <input
            disabled={!canWrite}
            value={shortDesc}
            onChange={(e) => setShortDesc(e.target.value)}
            placeholder="Resumo em uma linha"
            className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary disabled:opacity-60"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-nb-text">Descrição completa</label>
          <textarea
            disabled={!canWrite}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary resize-none disabled:opacity-60"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-nb-text">Preço</label>
            <input
              type="number"
              min="0"
              step="0.01"
              disabled={!canWrite}
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="0,00"
              className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary disabled:opacity-60"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-nb-text">Moeda</label>
            <select
              disabled={!canWrite}
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text focus:outline-none focus:ring-1 focus:ring-nb-primary disabled:opacity-60"
            >
              <option value="BRL">BRL (R$)</option>
              <option value="USD">USD ($)</option>
              <option value="EUR">EUR (€)</option>
            </select>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-nb-text">Status</label>
          <select
            disabled={!canWrite}
            value={status}
            onChange={(e) => setStatus(e.target.value as CatalogItemStatus)}
            className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text focus:outline-none focus:ring-1 focus:ring-nb-primary disabled:opacity-60"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-nb-text">SKU</label>
            <input
              disabled={!canWrite}
              value={sku}
              onChange={(e) => setSku(e.target.value)}
              placeholder="Ex: PROD-001"
              className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary disabled:opacity-60"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-nb-text">ID externo</label>
            <input
              disabled={!canWrite}
              value={externalId}
              onChange={(e) => setExternalId(e.target.value)}
              placeholder="ID no sistema externo"
              className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary disabled:opacity-60"
            />
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-nb-text">Estoque</label>
          <input
            type="number"
            min="0"
            disabled={!canWrite}
            value={stockQuantity}
            onChange={(e) => setStockQuantity(e.target.value)}
            placeholder="Deixe em branco se não controla estoque"
            className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary disabled:opacity-60"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-nb-text">Tags</label>
          <input
            disabled={!canWrite}
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="seminovo, automático, destaque (separar por vírgula)"
            className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary disabled:opacity-60"
          />
        </div>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            disabled={!canWrite}
            checked={isFeatured}
            onChange={(e) => setIsFeatured(e.target.checked)}
            className="w-4 h-4 rounded accent-nb-primary"
          />
          <span className="text-sm text-nb-text">Marcar como destaque</span>
        </label>

        {error && <p className="text-sm text-nb-danger">{error}</p>}

        {canWrite && (
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={saving || !name.trim()}
              className="flex items-center gap-2 px-5 py-2 rounded-xl bg-nb-primary text-white text-sm font-medium hover:bg-nb-primary-strong disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              Salvar
            </button>
            <Link
              href="/dashboard/catalog"
              className="px-5 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm font-medium text-nb-text hover:bg-nb-panel transition-colors"
            >
              Cancelar
            </Link>
          </div>
        )}
      </form>
    </div>
  );
}
