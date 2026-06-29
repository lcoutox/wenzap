"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Calendar,
  Package,
  Plus,
  Search,
  Star,
  Tag,
  Upload,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { CatalogCategory, CatalogItem, CatalogItemStatus, MemberRole } from "@/lib/api";

function canWrite(role: MemberRole | null) {
  return role === "owner" || role === "admin" || role === "member";
}

function StatusBadge({ status }: { status: CatalogItemStatus }) {
  const map: Record<CatalogItemStatus, { label: string; cls: string }> = {
    active:      { label: "Ativo",        cls: "bg-nb-success/10 text-nb-success border-nb-success/20" },
    draft:       { label: "Rascunho",     cls: "bg-nb-elevated   text-nb-muted   border-nb-border"     },
    inactive:    { label: "Inativo",      cls: "bg-nb-elevated   text-nb-muted   border-nb-border"     },
    unavailable: { label: "Indisponível", cls: "bg-nb-warning/10 text-nb-warning border-nb-warning/20" },
    archived:    { label: "Arquivado",    cls: "bg-nb-danger/10  text-nb-danger  border-nb-danger/20"  },
  };
  const s = map[status] ?? { label: status, cls: "bg-nb-elevated text-nb-muted border-nb-border" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${s.cls}`}>
      {s.label}
    </span>
  );
}

function formatPrice(price: number | null, currency: string) {
  if (price == null) return null;
  return price.toLocaleString("pt-BR", { style: "currency", currency });
}

function ItemThumbnail({ item }: { item: CatalogItem }) {
  const url = item.primary_media?.preview_url ?? null;

  if (url) {
    return (
      <div className="relative w-10 h-10 rounded-xl overflow-hidden flex-shrink-0 border border-nb-border">
        <Image src={url} alt={item.primary_media?.alt_text ?? ""} fill className="object-cover" unoptimized />
      </div>
    );
  }
  return (
    <div className="w-10 h-10 rounded-xl bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
      <Package className="w-5 h-5 text-nb-primary-strong" />
    </div>
  );
}

function ItemCard({
  item,
  categoryName,
}: {
  item: CatalogItem;
  categoryName?: string;
}) {
  return (
    <div className="group bg-nb-panel rounded-2xl border border-nb-border hover:border-nb-border-strong transition-all duration-150 flex flex-col">
      <div className="p-5 flex items-start gap-4">
        <ItemThumbnail item={item} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-nb-text truncate">{item.name}</h3>
            {item.is_featured && <Star className="w-3.5 h-3.5 text-nb-warning fill-nb-warning" />}
            <StatusBadge status={item.status} />
          </div>
          {item.short_description ? (
            <p className="mt-1 text-xs text-nb-muted line-clamp-2">{item.short_description}</p>
          ) : (
            <p className="mt-1 text-xs text-nb-muted/40 italic">Sem descrição</p>
          )}
          <div className="mt-2 flex items-center gap-3 flex-wrap">
            {formatPrice(item.price, item.currency) && (
              <span className="text-sm font-semibold text-nb-text">
                {formatPrice(item.price, item.currency)}
              </span>
            )}
            {categoryName && (
              <span className="inline-flex items-center gap-1 text-xs text-nb-muted">
                <Tag className="w-3 h-3" />
                {categoryName}
              </span>
            )}
            {item.sku && (
              <span className="text-xs text-nb-muted font-mono">SKU: {item.sku}</span>
            )}
          </div>
          {item.tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {item.tags.slice(0, 4).map((t) => (
                <span
                  key={t}
                  className="px-1.5 py-0.5 rounded text-xs bg-nb-elevated border border-nb-border text-nb-muted"
                >
                  {t}
                </span>
              ))}
              {item.tags.length > 4 && (
                <span className="px-1.5 py-0.5 rounded text-xs text-nb-muted">
                  +{item.tags.length - 4}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
      <div className="px-5 pb-4 mt-auto flex items-center justify-between border-t border-nb-border pt-3">
        <span className="flex items-center gap-1 text-xs text-nb-muted">
          <Calendar className="w-3 h-3" />
          {new Date(item.created_at).toLocaleDateString("pt-BR")}
        </span>
        <Link
          href={`/dashboard/catalog/${item.id}`}
          className="text-xs font-medium text-nb-primary hover:text-nb-primary-strong transition-colors"
        >
          Editar →
        </Link>
      </div>
    </div>
  );
}

export default function CatalogPage() {
  const [items, setItems]         = useState<CatalogItem[]>([]);
  const [categories, setCategories] = useState<CatalogCategory[]>([]);
  const [role, setRole]           = useState<MemberRole | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [q, setQ]                 = useState("");
  const [filterStatus, setFilterStatus] = useState<string>("active");

  useEffect(() => {
    Promise.all([
      api.me(),
      api.catalog.items.list({
        status: filterStatus as CatalogItemStatus,
        include_primary_media: true,
      }),
      api.catalog.categories.list(),
    ])
      .then(([me, fetchedItems, fetchedCats]) => {
        setRole(me.role);
        setItems(fetchedItems);
        setCategories(fetchedCats);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Erro ao carregar catálogo"))
      .finally(() => setLoading(false));
  }, [filterStatus]);

  const categoryMap = Object.fromEntries(categories.map((c) => [c.id, c.name]));

  const filtered = q.trim()
    ? items.filter((i) =>
        i.name.toLowerCase().includes(q.toLowerCase()) ||
        (i.short_description ?? "").toLowerCase().includes(q.toLowerCase()) ||
        (i.sku ?? "").toLowerCase().includes(q.toLowerCase()),
      )
    : items;

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-nb-text">Catálogo</h1>
          <p className="mt-0.5 text-sm text-nb-muted">
            Gerencie os produtos e serviços disponíveis para seus agentes.
          </p>
        </div>
        {canWrite(role) && (
          <div className="flex items-center gap-2">
            <Link
              href="/dashboard/catalog/import"
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm font-medium text-nb-text hover:bg-nb-border transition-colors"
            >
              <Upload className="w-4 h-4" />
              Importar
            </Link>
            <Link
              href="/dashboard/catalog/new"
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-nb-primary text-white text-sm font-medium hover:bg-nb-primary-strong transition-colors"
            >
              <Plus className="w-4 h-4" />
              Novo item
            </Link>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-48 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-nb-muted" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por nome, descrição ou SKU…"
            className="w-full pl-9 pr-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary"
          />
        </div>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text focus:outline-none focus:ring-1 focus:ring-nb-primary"
        >
          <option value="">Todos os status</option>
          <option value="active">Ativo</option>
          <option value="draft">Rascunho</option>
          <option value="inactive">Inativo</option>
          <option value="unavailable">Indisponível</option>
        </select>
      </div>

      {/* Content */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-44 rounded-2xl bg-nb-elevated animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <p className="text-sm text-nb-danger">{error}</p>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
          <div className="w-16 h-16 rounded-2xl bg-nb-elevated border border-nb-border flex items-center justify-center">
            <Package className="w-8 h-8 text-nb-muted" />
          </div>
          <div>
            <p className="text-sm font-medium text-nb-text">Nenhum item encontrado</p>
            <p className="text-xs text-nb-muted mt-1">
              {q ? "Tente outros termos de busca." : "Crie o primeiro item do catálogo."}
            </p>
          </div>
          {canWrite(role) && !q && (
            <Link
              href="/dashboard/catalog/new"
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-nb-primary text-white text-sm font-medium hover:bg-nb-primary-strong transition-colors"
            >
              <Plus className="w-4 h-4" />
              Novo item
            </Link>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((item) => (
            <ItemCard
              key={item.id}
              item={item}
              categoryName={item.category_id ? categoryMap[item.category_id] : undefined}
            />
          ))}
        </div>
      )}
    </div>
  );
}
