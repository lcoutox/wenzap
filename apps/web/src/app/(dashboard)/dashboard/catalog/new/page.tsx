"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { CatalogCategory, CatalogItemStatus } from "@/lib/api";

const STATUS_OPTIONS: { value: CatalogItemStatus; label: string }[] = [
  { value: "active",      label: "Ativo"        },
  { value: "draft",       label: "Rascunho"     },
  { value: "inactive",    label: "Inativo"      },
  { value: "unavailable", label: "Indisponível" },
];

export default function NewCatalogItemPage() {
  const router = useRouter();
  const [categories, setCategories] = useState<CatalogCategory[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName]                     = useState("");
  const [categoryId, setCategoryId]         = useState("");
  const [shortDesc, setShortDesc]           = useState("");
  const [description, setDescription]       = useState("");
  const [price, setPrice]                   = useState("");
  const [currency, setCurrency]             = useState("BRL");
  const [status, setStatus]                 = useState<CatalogItemStatus>("active");
  const [sku, setSku]                       = useState("");
  const [externalId, setExternalId]         = useState("");
  const [tags, setTags]                     = useState("");
  const [isFeatured, setIsFeatured]         = useState(false);
  const [stockQuantity, setStockQuantity]   = useState("");

  useEffect(() => {
    api.catalog.categories.list().then(setCategories).catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const item = await api.catalog.items.create({
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
      router.push(`/dashboard/catalog/${item.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao criar item");
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <div className="flex items-center gap-3">
        <Link
          href="/dashboard/catalog"
          className="p-2 rounded-xl hover:bg-nb-elevated transition-colors"
        >
          <ArrowLeft className="w-4 h-4 text-nb-muted" />
        </Link>
        <h1 className="text-xl font-bold text-nb-text">Novo item do catálogo</h1>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        {/* Name */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-nb-text">
            Nome <span className="text-nb-danger">*</span>
          </label>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ex: Corolla XEI 2021"
            className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary"
          />
        </div>

        {/* Category */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-nb-text">Categoria</label>
          <select
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text focus:outline-none focus:ring-1 focus:ring-nb-primary"
          >
            <option value="">Sem categoria</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>

        {/* Short description */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-nb-text">Descrição curta</label>
          <input
            value={shortDesc}
            onChange={(e) => setShortDesc(e.target.value)}
            placeholder="Resumo em uma linha"
            className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary"
          />
        </div>

        {/* Description */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-nb-text">Descrição completa</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Detalhes do produto ou serviço"
            rows={4}
            className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary resize-none"
          />
        </div>

        {/* Price + Currency */}
        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-nb-text">Preço</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="0,00"
              className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-nb-text">Moeda</label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text focus:outline-none focus:ring-1 focus:ring-nb-primary"
            >
              <option value="BRL">BRL (R$)</option>
              <option value="USD">USD ($)</option>
              <option value="EUR">EUR (€)</option>
            </select>
          </div>
        </div>

        {/* Status */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-nb-text">Status</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as CatalogItemStatus)}
            className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text focus:outline-none focus:ring-1 focus:ring-nb-primary"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        {/* SKU + External ID */}
        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-nb-text">SKU</label>
            <input
              value={sku}
              onChange={(e) => setSku(e.target.value)}
              placeholder="Ex: PROD-001"
              className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-nb-text">ID externo</label>
            <input
              value={externalId}
              onChange={(e) => setExternalId(e.target.value)}
              placeholder="ID no sistema externo"
              className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary"
            />
          </div>
        </div>

        {/* Stock */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-nb-text">Estoque</label>
          <input
            type="number"
            min="0"
            value={stockQuantity}
            onChange={(e) => setStockQuantity(e.target.value)}
            placeholder="Deixe em branco se não controla estoque"
            className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary"
          />
        </div>

        {/* Tags */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-nb-text">Tags</label>
          <input
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="seminovo, automático, destaque (separar por vírgula)"
            className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary"
          />
        </div>

        {/* Featured */}
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={isFeatured}
            onChange={(e) => setIsFeatured(e.target.checked)}
            className="w-4 h-4 rounded accent-nb-primary"
          />
          <span className="text-sm text-nb-text">Marcar como destaque</span>
        </label>

        {error && <p className="text-sm text-nb-danger">{error}</p>}

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={saving || !name.trim()}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-nb-primary text-white text-sm font-medium hover:bg-nb-primary-strong disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            Criar item
          </button>
          <Link
            href="/dashboard/catalog"
            className="px-5 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm font-medium text-nb-text hover:bg-nb-panel transition-colors"
          >
            Cancelar
          </Link>
        </div>
      </form>
    </div>
  );
}
