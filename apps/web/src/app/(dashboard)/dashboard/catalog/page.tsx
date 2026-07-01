"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import {
  Calendar,
  FolderOpen,
  Inbox,
  Package,
  Pencil,
  Plus,
  Search,
  Star,
  Tag,
  Upload,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { CatalogCategory, CatalogItem, CatalogItemStatus, MemberRole, Plan, Usage } from "@/lib/api";
import { canCreateResource } from "@/lib/plan";
import { CatalogCategoryFormModal } from "@/components/catalog/CatalogCategoryFormModal";

// ── Helpers ───────────────────────────────────────────────────────────────────

function canWrite(role: MemberRole | null) {
  return role === "owner" || role === "admin" || role === "member";
}

function formatPrice(price: number | null, currency: string) {
  if (price == null) return null;
  return price.toLocaleString("pt-BR", { style: "currency", currency });
}

// ── Shared sub-components ─────────────────────────────────────────────────────

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

function ItemThumbnail({ item, size = "sm" }: { item: CatalogItem; size?: "sm" | "xs" }) {
  const url = item.primary_media?.preview_url ?? null;
  const dim = size === "xs" ? "w-8 h-8" : "w-10 h-10";
  if (url) {
    return (
      <div className={`relative ${dim} rounded-lg overflow-hidden flex-shrink-0 border border-nb-border`}>
        <Image src={url} alt={item.primary_media?.alt_text ?? ""} fill className="object-cover" unoptimized />
      </div>
    );
  }
  return (
    <div className={`${dim} rounded-lg bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center flex-shrink-0`}>
      <Package className="w-4 h-4 text-nb-primary-strong" />
    </div>
  );
}

// ── Category card ─────────────────────────────────────────────────────────────

function CatalogCategoryCard({
  category,
  activeCount,
  totalCount,
  writeAllowed,
  onViewItems,
  onEdit,
  onToggleActive,
}: {
  category: CatalogCategory;
  activeCount: number;
  totalCount: number;
  writeAllowed: boolean;
  onViewItems: () => void;
  onEdit: () => void;
  onToggleActive: () => void;
}) {
  const [toggling, setToggling] = useState(false);

  async function handleToggle() {
    setToggling(true);
    try { await onToggleActive(); } finally { setToggling(false); }
  }

  return (
    <div className={`bg-nb-panel rounded-2xl border flex flex-col transition-all ${
      category.is_active ? "border-nb-border hover:border-nb-border-strong" : "border-nb-border opacity-60"
    }`}>
      <div className="p-5 flex-1 flex flex-col gap-3">
        {/* Top row */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 flex-wrap min-w-0">
            <div className="w-8 h-8 rounded-xl bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
              <FolderOpen className="w-4 h-4 text-nb-primary-strong" />
            </div>
            <h3 className="text-sm font-semibold text-nb-text truncate">{category.name}</h3>
          </div>
          <span className={`flex-shrink-0 px-2 py-0.5 text-xs font-medium rounded-full border ${
            category.is_active
              ? "bg-nb-success/10 text-nb-success border-nb-success/20"
              : "bg-nb-elevated text-nb-muted border-nb-border"
          }`}>
            {category.is_active ? "Ativa" : "Inativa"}
          </span>
        </div>

        {/* Description */}
        {category.description ? (
          <p className="text-xs text-nb-muted leading-relaxed line-clamp-2">{category.description}</p>
        ) : (
          <p className="text-xs text-nb-muted/50 italic">Sem descrição</p>
        )}

        {/* Counts */}
        <div className="flex items-center gap-3 text-xs text-nb-muted">
          <span className="flex items-center gap-1">
            <span className="font-semibold text-nb-text">{activeCount}</span>
            {activeCount === 1 ? "item ativo" : "itens ativos"}
          </span>
          {totalCount !== activeCount && (
            <span className="text-nb-muted/60">· {totalCount} total</span>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="px-5 py-3 border-t border-nb-border flex items-center gap-2">
        <button
          type="button"
          onClick={onViewItems}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary/10 transition-colors"
        >
          Ver itens
        </button>
        {writeAllowed && (
          <>
            <button
              type="button"
              onClick={onEdit}
              title="Editar"
              className="p-1.5 rounded-xl border border-nb-border text-nb-muted hover:bg-nb-elevated hover:text-nb-text transition-colors"
            >
              <Pencil className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={handleToggle}
              disabled={toggling}
              className="px-2.5 py-1.5 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors disabled:opacity-50"
            >
              {category.is_active ? "Desativar" : "Ativar"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ── Uncategorized virtual card ─────────────────────────────────────────────────

function UncategorizedCard({
  count,
  onViewItems,
}: {
  count: number;
  onViewItems: () => void;
}) {
  return (
    <div className="bg-nb-panel rounded-2xl border border-dashed border-nb-border flex flex-col">
      <div className="p-5 flex-1 flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
            <Inbox className="w-4 h-4 text-nb-muted" />
          </div>
          <h3 className="text-sm font-semibold text-nb-secondary">Sem categoria</h3>
        </div>
        <p className="text-xs text-nb-muted leading-relaxed">
          Itens que ainda não foram organizados em nenhuma categoria.
        </p>
        <p className="text-xs text-nb-muted">
          <span className="font-semibold text-nb-text">{count}</span>{" "}
          {count === 1 ? "item" : "itens"}
        </p>
      </div>
      <div className="px-5 py-3 border-t border-nb-border">
        <button
          type="button"
          onClick={onViewItems}
          className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-elevated hover:text-nb-text transition-colors"
        >
          Ver itens
        </button>
      </div>
    </div>
  );
}

// ── Items table ───────────────────────────────────────────────────────────────

function ItemsTable({
  items,
  categories,
  loading,
}: {
  items: CatalogItem[];
  categories: CatalogCategory[];
  loading: boolean;
}) {
  const categoryMap = useMemo(
    () => Object.fromEntries(categories.map((c) => [c.id, c.name])),
    [categories],
  );

  if (loading) {
    return (
      <div className="space-y-2">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-14 rounded-xl bg-nb-elevated animate-pulse" />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-4 text-center border border-dashed border-nb-border rounded-2xl">
        <div className="w-12 h-12 rounded-2xl bg-nb-elevated border border-nb-border flex items-center justify-center">
          <Package className="w-6 h-6 text-nb-muted" />
        </div>
        <div>
          <p className="text-sm font-medium text-nb-text">Nenhum item encontrado</p>
          <p className="text-xs text-nb-muted mt-1">Tente ajustar os filtros ou crie um novo item.</p>
        </div>
        <Link
          href="/dashboard/catalog/new"
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-nb-primary text-white text-sm font-medium hover:bg-nb-primary-strong transition-colors"
        >
          <Plus className="w-4 h-4" />
          Novo item
        </Link>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-nb-border overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-nb-border bg-nb-elevated">
            <th className="text-left px-4 py-3 text-xs font-semibold text-nb-muted w-8" />
            <th className="text-left px-4 py-3 text-xs font-semibold text-nb-muted">Nome</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-nb-muted hidden md:table-cell">Categoria</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-nb-muted hidden sm:table-cell">Preço</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-nb-muted">Status</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-nb-muted hidden lg:table-cell">Tags</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-nb-muted hidden xl:table-cell">Atualizado</th>
            <th className="px-4 py-3 w-16" />
          </tr>
        </thead>
        <tbody className="divide-y divide-nb-border">
          {items.map((item) => (
            <tr key={item.id} className="bg-nb-panel hover:bg-nb-elevated/50 transition-colors group">
              <td className="px-4 py-3">
                <ItemThumbnail item={item} size="xs" />
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="font-medium text-nb-text truncate max-w-[200px]">{item.name}</span>
                  {item.is_featured && <Star className="w-3 h-3 text-nb-warning fill-nb-warning flex-shrink-0" />}
                </div>
                {item.short_description && (
                  <p className="text-xs text-nb-muted truncate max-w-[200px] mt-0.5">{item.short_description}</p>
                )}
              </td>
              <td className="px-4 py-3 hidden md:table-cell">
                {item.category_id ? (
                  <span className="inline-flex items-center gap-1 text-xs text-nb-muted">
                    <Tag className="w-3 h-3" />
                    {categoryMap[item.category_id] ?? "—"}
                  </span>
                ) : (
                  <span className="text-xs text-nb-muted/50 italic">Sem categoria</span>
                )}
              </td>
              <td className="px-4 py-3 hidden sm:table-cell">
                <span className="text-sm font-medium text-nb-text">
                  {formatPrice(item.price, item.currency) ?? <span className="text-nb-muted/50 text-xs italic font-normal">—</span>}
                </span>
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={item.status} />
              </td>
              <td className="px-4 py-3 hidden lg:table-cell">
                <div className="flex flex-wrap gap-1 max-w-[140px]">
                  {item.tags.slice(0, 3).map((t) => (
                    <span key={t} className="px-1.5 py-0.5 rounded text-xs bg-nb-elevated border border-nb-border text-nb-muted">
                      {t}
                    </span>
                  ))}
                  {item.tags.length > 3 && (
                    <span className="text-xs text-nb-muted">+{item.tags.length - 3}</span>
                  )}
                </div>
              </td>
              <td className="px-4 py-3 hidden xl:table-cell">
                <span className="flex items-center gap-1 text-xs text-nb-muted">
                  <Calendar className="w-3 h-3" />
                  {new Date(item.updated_at).toLocaleDateString("pt-BR")}
                </span>
              </td>
              <td className="px-4 py-3 text-right">
                <Link
                  href={`/dashboard/catalog/${item.id}`}
                  className="text-xs font-medium text-nb-primary hover:text-nb-primary-strong transition-colors opacity-0 group-hover:opacity-100"
                >
                  Editar
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type CatalogTab = "categories" | "items";

function CatalogPageContent() {
  const router       = useRouter();
  const searchParams = useSearchParams();

  // Data
  const [items,      setItems]      = useState<CatalogItem[]>([]);
  const [categories, setCategories] = useState<CatalogCategory[]>([]);
  const [role,       setRole]       = useState<MemberRole | null>(null);
  const [plan,       setPlan]       = useState<Plan | null>(null);
  const [usage,      setUsage]      = useState<Usage | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState<string | null>(null);

  // Tab + category filter from URL
  const tabParam      = searchParams.get("tab") as CatalogTab | null;
  const categoryParam = searchParams.get("category"); // category id or "uncategorized"
  const activeTab: CatalogTab = tabParam === "items" ? "items" : "categories";

  // Items tab filters (client-side)
  const [q,            setQ]            = useState("");
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [filterCat,    setFilterCat]    = useState<string>(categoryParam ?? "");

  // Sync URL category param → filter state when switching to items tab via "Ver itens"
  useEffect(() => {
    if (categoryParam !== null) setFilterCat(categoryParam);
  }, [categoryParam]);

  // Category form modal
  const [catModalOpen,    setCatModalOpen]    = useState(false);
  const [editingCategory, setEditingCategory] = useState<CatalogCategory | undefined>();

  // Load
  useEffect(() => {
    Promise.all([
      api.me(),
      api.catalog.items.list({ include_primary_media: true }),
      api.catalog.categories.list(true), // include inactive for management
      api.plans.current().catch(() => null),
      api.plans.usage().catch(() => null),
    ])
      .then(([me, fetchedItems, fetchedCats, sub, usageData]) => {
        setRole(me.role);
        setItems(fetchedItems);
        setCategories(fetchedCats);
        setPlan(sub?.plan ?? null);
        setUsage(usageData);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Erro ao carregar catálogo."))
      .finally(() => setLoading(false));
  }, []);

  // Counts per category (all items, not filtered)
  const countsByCategory = useMemo(() => {
    const active: Record<string, number> = {};
    const total:  Record<string, number> = {};
    for (const item of items) {
      const key = item.category_id ?? "__none__";
      total[key]  = (total[key]  ?? 0) + 1;
      if (item.status === "active") active[key] = (active[key] ?? 0) + 1;
    }
    return { active, total };
  }, [items]);

  const uncategorizedCount = countsByCategory.total["__none__"] ?? 0;

  // Active categories only (for display)
  const activeCategories = categories.filter((c) => c.is_active);

  // Items tab filtered list
  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      if (filterCat === "uncategorized" && item.category_id !== null) return false;
      if (filterCat && filterCat !== "uncategorized" && item.category_id !== filterCat) return false;
      if (filterStatus && item.status !== filterStatus) return false;
      if (q.trim()) {
        const lq = q.toLowerCase();
        return (
          item.name.toLowerCase().includes(lq) ||
          (item.short_description ?? "").toLowerCase().includes(lq) ||
          (item.sku ?? "").toLowerCase().includes(lq)
        );
      }
      return true;
    });
  }, [items, filterCat, filterStatus, q]);

  // Navigation helpers
  function goToTab(tab: CatalogTab, extra?: Record<string, string>) {
    const p = new URLSearchParams();
    p.set("tab", tab);
    if (extra) for (const [k, v] of Object.entries(extra)) p.set(k, v);
    router.push(`/dashboard/catalog?${p.toString()}`);
  }

  function handleViewItems(categoryId: string | "uncategorized") {
    setFilterCat(categoryId);
    setQ("");
    setFilterStatus("");
    goToTab("items", { category: categoryId });
  }

  // Category CRUD
  function handleCategorySaved(saved: CatalogCategory) {
    setCategories((prev) => {
      const idx = prev.findIndex((c) => c.id === saved.id);
      return idx >= 0 ? prev.map((c) => (c.id === saved.id ? saved : c)) : [...prev, saved];
    });
  }

  async function handleToggleCategory(cat: CatalogCategory) {
    const updated = await api.catalog.categories.update(cat.id, { is_active: !cat.is_active });
    setCategories((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  }

  function openCreateModal() {
    setEditingCategory(undefined);
    setCatModalOpen(true);
  }

  function openEditModal(cat: CatalogCategory) {
    setEditingCategory(cat);
    setCatModalOpen(true);
  }

  const write = canWrite(role);

  // Summary numbers
  const totalActive    = items.filter((i) => i.status === "active").length;
  const catalogUsed    = usage?.catalog_items_count ?? items.filter((i) => i.status !== "archived").length;
  const catalogLimit   = plan?.catalog_items_limit ?? 0;
  const catalogAtLimit = catalogLimit > 0 && !canCreateResource(catalogUsed, catalogLimit);

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-nb-text">Catálogo</h1>
          <p className="mt-0.5 text-sm text-nb-muted">
            Organize produtos, serviços, planos e ofertas que seus agentes podem consultar durante o atendimento.
          </p>
        </div>
        {write && (
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={openCreateModal}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-nb-primary text-white text-sm font-medium hover:bg-nb-primary-strong transition-colors"
            >
              <Plus className="w-4 h-4" />
              Nova categoria
            </button>
            <Link
              href="/dashboard/catalog/new"
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm font-medium text-nb-text hover:bg-nb-border transition-colors"
            >
              <Plus className="w-4 h-4" />
              Novo item
            </Link>
            <Link
              href="/dashboard/catalog/import"
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm font-medium text-nb-text hover:bg-nb-border transition-colors"
            >
              <Upload className="w-4 h-4" />
              Importar
            </Link>
          </div>
        )}
      </div>

      {/* Summary chips */}
      {!loading && !error && (
        <div className="flex items-center gap-3 flex-wrap text-xs text-nb-muted">
          <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-nb-elevated border border-nb-border">
            <FolderOpen className="w-3.5 h-3.5" />
            <span><span className="font-semibold text-nb-text">{activeCategories.length}</span> {activeCategories.length === 1 ? "categoria" : "categorias"}</span>
          </span>
          <span className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border ${catalogAtLimit ? "bg-nb-danger/5 border-nb-danger/20 text-nb-danger" : "bg-nb-elevated border-nb-border"}`}>
            <Package className="w-3.5 h-3.5" />
            {catalogLimit > 0 ? (
              <span>
                <span className="font-semibold text-nb-text">{catalogUsed}</span>
                <span className="text-nb-muted"> / {catalogLimit} itens</span>
                {catalogAtLimit && <span className="ml-1 font-semibold text-nb-danger">— limite atingido</span>}
              </span>
            ) : (
              <span><span className="font-semibold text-nb-text">{totalActive}</span> itens ativos</span>
            )}
          </span>
          {uncategorizedCount > 0 && (
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-nb-warning/10 border border-nb-warning/20 text-nb-warning">
              <Inbox className="w-3.5 h-3.5" />
              <span><span className="font-semibold">{uncategorizedCount}</span> sem categoria</span>
            </span>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-nb-border -mb-2">
        <nav className="flex gap-0 -mb-px">
          {(["categories", "items"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => goToTab(tab)}
              className={`flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
                  ? "border-nb-primary text-nb-primary-strong"
                  : "border-transparent text-nb-muted hover:text-nb-secondary hover:border-nb-border-strong"
              }`}
            >
              {tab === "categories" ? <><FolderOpen className="w-4 h-4" />Categorias</> : <><Package className="w-4 h-4" />Todos os itens</>}
            </button>
          ))}
        </nav>
      </div>

      {/* ── Categories tab ──────────────────────────────────────────────────── */}
      {activeTab === "categories" && (
        <>
          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-44 rounded-2xl bg-nb-elevated animate-pulse" />
              ))}
            </div>
          ) : error ? (
            <p className="text-sm text-nb-danger">{error}</p>
          ) : activeCategories.length === 0 && uncategorizedCount === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
              <div className="w-16 h-16 rounded-2xl bg-nb-elevated border border-nb-border flex items-center justify-center">
                <FolderOpen className="w-8 h-8 text-nb-muted" />
              </div>
              <div>
                <p className="text-sm font-medium text-nb-text">Nenhuma categoria criada.</p>
                <p className="text-xs text-nb-muted mt-1 max-w-xs">
                  Crie categorias para organizar os itens do seu Catálogo e controlar o que cada agente pode consultar.
                </p>
              </div>
              {write && (
                <button
                  onClick={openCreateModal}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-nb-primary text-white text-sm font-medium hover:bg-nb-primary-strong transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  Criar primeira categoria
                </button>
              )}
            </div>
          ) : (
            <>
              {/* Microcopy */}
              <p className="text-xs text-nb-muted">
                As categorias também podem ser usadas para definir quais itens cada agente pode consultar.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {activeCategories.map((cat) => (
                  <CatalogCategoryCard
                    key={cat.id}
                    category={cat}
                    activeCount={countsByCategory.active[cat.id] ?? 0}
                    totalCount={countsByCategory.total[cat.id] ?? 0}
                    writeAllowed={write}
                    onViewItems={() => handleViewItems(cat.id)}
                    onEdit={() => openEditModal(cat)}
                    onToggleActive={() => handleToggleCategory(cat)}
                  />
                ))}

                {/* Uncategorized virtual card */}
                {uncategorizedCount > 0 && (
                  <UncategorizedCard
                    count={uncategorizedCount}
                    onViewItems={() => handleViewItems("uncategorized")}
                  />
                )}
              </div>

              {/* Show inactive categories if any */}
              {categories.some((c) => !c.is_active) && (
                <div className="mt-2">
                  <p className="text-xs font-semibold text-nb-muted uppercase tracking-wide mb-3">
                    Categorias inativas
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {categories.filter((c) => !c.is_active).map((cat) => (
                      <CatalogCategoryCard
                        key={cat.id}
                        category={cat}
                        activeCount={countsByCategory.active[cat.id] ?? 0}
                        totalCount={countsByCategory.total[cat.id] ?? 0}
                        writeAllowed={write}
                        onViewItems={() => handleViewItems(cat.id)}
                        onEdit={() => openEditModal(cat)}
                        onToggleActive={() => handleToggleCategory(cat)}
                      />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* ── Items tab ───────────────────────────────────────────────────────── */}
      {activeTab === "items" && (
        <>
          {/* Filters */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="relative flex-1 min-w-48 max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-nb-muted pointer-events-none" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Buscar por nome, descrição ou SKU…"
                className="w-full pl-9 pr-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-primary"
              />
            </div>
            <select
              value={filterCat}
              onChange={(e) => setFilterCat(e.target.value)}
              className="px-3 py-2 rounded-xl bg-nb-elevated border border-nb-border text-sm text-nb-text focus:outline-none focus:ring-1 focus:ring-nb-primary"
            >
              <option value="">Todas as categorias</option>
              {categories.filter((c) => c.is_active).map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
              <option value="uncategorized">Sem categoria</option>
            </select>
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
            {(filterCat || filterStatus || q) && (
              <button
                type="button"
                onClick={() => { setQ(""); setFilterCat(""); setFilterStatus(""); }}
                className="text-xs text-nb-muted hover:text-nb-text transition-colors"
              >
                Limpar filtros
              </button>
            )}
          </div>

          {/* Active filter label */}
          {filterCat && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-nb-muted">Filtrando por:</span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-nb-primary/10 border border-nb-primary/20 text-xs font-medium text-nb-primary">
                <FolderOpen className="w-3 h-3" />
                {filterCat === "uncategorized"
                  ? "Sem categoria"
                  : (categories.find((c) => c.id === filterCat)?.name ?? filterCat)}
                <button
                  type="button"
                  onClick={() => setFilterCat("")}
                  className="ml-0.5 hover:text-nb-primary-strong"
                >
                  ×
                </button>
              </span>
            </div>
          )}

          <ItemsTable
            items={filteredItems}
            categories={categories}
            loading={loading}
          />
        </>
      )}

      {/* Category form modal */}
      <CatalogCategoryFormModal
        open={catModalOpen}
        onClose={() => setCatModalOpen(false)}
        category={editingCategory}
        onSaved={handleCategorySaved}
      />
    </div>
  );
}

export default function CatalogPage() {
  return (
    <Suspense>
      <CatalogPageContent />
    </Suspense>
  );
}
