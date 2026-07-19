"""
Catalog Retrieval Service — Catálogo.3.

Provides intent-based retrieval of catalog items for injection into the LLM
context before generating agent responses.

Design decisions:
  - Intent detection via keyword matching (no embedding required in this phase).
  - Retrieval uses ILIKE on searchable_text, name, short_description, and tags
    for multi-term ranking. pgvector/semantic search can be layered later.
  - Only items with status="active" are eligible.
  - Workspace isolation is enforced at the query level.
  - Never raises: errors are captured in CatalogRetrievalResult.error_message.
  - signed/presigned URLs are NOT generated — the LLM only needs to know whether
    primary media is available (boolean), not the actual URL.
"""

import logging
import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalog_category import CatalogCategory
from app.models.catalog_item import CatalogItem
from app.models.catalog_media import CatalogMedia
from app.services.embedding_providers.base import EmbeddingError, EmbeddingProvider

logger = logging.getLogger(__name__)

# ── Intent detection ──────────────────────────────────────────────────────────

# Commercial keywords that signal the user is asking about products/services.
# Covers Portuguese and common English terms.
_COMMERCIAL_KEYWORDS: frozenset[str] = frozenset({
    # Portuguese — existence / availability
    "tem", "têm", "vocês têm", "disponível", "disponibilidade", "oferece",
    "oferecem", "vendem", "vende", "trabalham com", "trabalha com",
    # Portuguese — commercial terms
    "preço", "valor", "custo", "quanto", "quanto custa", "pagar",
    "plano", "planos", "pacote", "pacotes", "oferta", "ofertas",
    "produto", "produtos", "serviço", "serviços",
    "opção", "opções", "alternativa", "alternativas",
    "modelo", "modelos", "versão", "versões",
    # Portuguese — specific categories
    "carro", "carros", "veículo", "veículos", "automóvel", "automóveis",
    "apartamento", "apartamentos", "imóvel", "imóveis", "casa", "casas",
    "curso", "cursos", "aula", "aulas", "treinamento", "treinamentos",
    "procedimento", "procedimentos", "tratamento", "tratamentos",
    "plano de saúde", "seguro",
    # Portuguese — qualifying terms
    "mais barato", "mais caro", "econômico", "básico", "premium",
    "completo", "simples", "barato", "barata",
    # English
    "price", "cost", "plan", "plans", "product", "products",
    "service", "services", "package", "packages", "offer", "available",
    "do you have", "have you", "how much",
})


def should_retrieve_catalog(message: str) -> bool:
    """
    Return True if the message appears to involve a commercial intent
    that warrants a catalog lookup.

    Uses simple keyword matching — intentionally conservative to avoid
    injecting catalog data into unrelated messages (greetings, support, etc.).
    """
    lower = message.lower()
    return any(kw in lower for kw in _COMMERCIAL_KEYWORDS)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class CatalogRetrievalItem:
    """A single catalog item as returned by the retrieval service."""
    id: uuid.UUID
    name: str
    category_name: str | None
    short_description: str | None
    price: float | None
    currency: str
    tags: list[str]
    metadata_json: dict
    primary_media_available: bool
    score: float                  # Final combined score (0–1)
    semantic_score: float | None = None   # Cosine similarity score (0–1)
    lexical_score: float | None = None    # Normalised term-match score (0–1)
    retrieval_method: str = "lexical"     # "hybrid" | "lexical" | "lexical_fallback"


@dataclass
class CatalogRetrievalResult:
    """Result of a catalog retrieval call."""
    items: list[CatalogRetrievalItem] = field(default_factory=list)
    context_block: str | None = None
    retrieval_attempted: bool = False
    error_message: str | None = None
    # For audit / metadata_json logging
    query: str = ""


# ── Retrieval ─────────────────────────────────────────────────────────────────

_DEFAULT_LIMIT = 3
_MAX_LIMIT = 20
_MIN_TERM_LENGTH = 2

# catalog-retrieval-robustness-prd.md — Camada 1: below this char budget, skip
# ranking entirely and inject the whole active catalog (respecting category
# scope). ~6000 chars ≈ 1500 tokens, comfortably covers 15-20 typical items —
# the point where retrieval quality matters least (few candidates, low risk
# of a real match scoring low) and full injection matters most (zero risk of
# "forgetting" an item, unlike top-K ranking with noisy scores).
_FULL_CATALOG_CHAR_BUDGET = 6000
_ITEM_FORMAT_OVERHEAD_CHARS = 80  # rough per-item cost of labels/formatting in the context block

# Camada 2 — Reciprocal Rank Fusion constant (k=60 is the standard from the
# original RRF paper; not sensitive to tuning, works well across corpus sizes
# without per-catalog calibration — unlike a fixed weighted-sum of raw scores).
_RRF_K = 60

# Camada 2 — confidence floor. A candidate only survives if its semantic
# cosine similarity clears this bar, OR it has a genuine full-text match
# (Postgres FTS only returns rows that actually match the tsquery — never a
# "kind of similar" false positive the way a weak embedding score can be).
# Tuned conservatively; revisit if real catalogs show this rejecting good
# matches or letting weak ones through.
_SEMANTIC_CONFIDENCE_FLOOR = 0.15

# Postgres text-search configuration — 'portuguese' stems/handles accents
# correctly for the platform's primary language (pt-BR only, per CLAUDE.md).
_FTS_CONFIG = "portuguese"

# Numeric values that look like prices ("90 mil", "89500", "88.900").
_PRICE_PATTERN = re.compile(r"(\d[\d.,]*)\s*(mil|k)?", re.IGNORECASE)


def _extract_terms(query: str) -> list[str]:
    """Tokenise the query into searchable terms, filtering short stop-words."""
    cleaned = re.sub(r"[!?;:()\[\]\"'`]", " ", query.lower())
    tokens = cleaned.split()
    return [t for t in tokens if len(t) >= _MIN_TERM_LENGTH]


def _resolve_support_data(
    db: Session,
    workspace_id: uuid.UUID,
    rows: list[CatalogItem],
) -> tuple[dict[uuid.UUID, str], set[uuid.UUID]]:
    """Resolve category names and primary-media flags in 2 bulk queries."""
    cat_ids = {r.category_id for r in rows if r.category_id}
    cat_map: dict[uuid.UUID, str] = {}
    if cat_ids:
        cats = db.scalars(
            select(CatalogCategory).where(CatalogCategory.id.in_(cat_ids))
        ).all()
        cat_map = {c.id: c.name for c in cats}

    item_ids = [r.id for r in rows]
    primary_media_ids: set[uuid.UUID] = set(
        db.scalars(
            select(CatalogMedia.item_id).where(
                CatalogMedia.item_id.in_(item_ids),
                CatalogMedia.workspace_id == workspace_id,
                CatalogMedia.is_primary == True,  # noqa: E712
                CatalogMedia.file_type == "image",
            )
        ).all()
    )
    return cat_map, primary_media_ids


def _to_retrieval_item(
    item: CatalogItem,
    cat_map: dict[uuid.UUID, str],
    primary_media_ids: set[uuid.UUID],
    score: float,
    semantic_score: float | None = None,
    lexical_score: float | None = None,
    retrieval_method: str = "lexical",
) -> CatalogRetrievalItem:
    return CatalogRetrievalItem(
        id=item.id,
        name=item.name,
        category_name=cat_map.get(item.category_id) if item.category_id else None,
        short_description=item.short_description,
        price=float(item.price) if item.price is not None else None,
        currency=item.currency,
        tags=list(item.tags or []),
        metadata_json=dict(item.metadata_json or {}),
        primary_media_available=item.id in primary_media_ids,
        score=score,
        semantic_score=semantic_score,
        lexical_score=lexical_score,
        retrieval_method=retrieval_method,
    )


def _category_filter(allowed_category_ids: list[uuid.UUID] | None):
    """
    Return a SQLAlchemy clause restricting items to allowed categories, or None.

    None  → no filter (all scope)
    []    → block all (selected scope, but no categories chosen)
    [ids] → IN filter
    """
    if allowed_category_ids is None:
        return None
    if not allowed_category_ids:
        # Empty selected list → nothing should match
        from sqlalchemy import false
        return false()
    return CatalogItem.category_id.in_(allowed_category_ids)


def _fts_document():
    """
    The tsvector expression used both to query and to build the GIN index
    (catalog-retrieval-robustness-prd.md, migration 074) — must match the
    index definition exactly (same config, same source column) or Postgres
    falls back to a sequential scan instead of using the index.
    """
    return func.to_tsvector(_FTS_CONFIG, func.coalesce(CatalogItem.searchable_text, ""))


def _fulltext_search(
    db: Session,
    workspace_id: uuid.UUID,
    query: str,
    over_fetch: int,
    allowed_category_ids: list[uuid.UUID] | None = None,
) -> list[tuple[CatalogItem, float]]:
    """
    Native Postgres full-text search (replaces the old ILIKE term-counting) —
    returns (item, ts_rank) pairs ordered by rank desc. Only rows that
    genuinely match the tsquery are returned (no "kind of similar" false
    positives the way weak embedding scores can produce), which is exactly
    what makes a hit here a reliable confidence signal in
    _passes_confidence_floor below.
    """
    tsquery = func.plainto_tsquery(_FTS_CONFIG, query)
    document = _fts_document()
    where_clauses = [
        CatalogItem.workspace_id == workspace_id,
        CatalogItem.status == "active",
        document.op("@@")(tsquery),
    ]
    cat_filter = _category_filter(allowed_category_ids)
    if cat_filter is not None:
        where_clauses.append(cat_filter)
    rank = func.ts_rank(document, tsquery)
    rows = db.execute(
        select(CatalogItem, rank.label("rank"))
        .where(*where_clauses)
        .order_by(rank.desc())
        .limit(over_fetch)
    ).all()
    return [(row.CatalogItem, float(row.rank)) for row in rows]


def _semantic_search(
    db: Session,
    workspace_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int,
    allowed_category_ids: list[uuid.UUID] | None = None,
) -> list[tuple[CatalogItem, float]]:
    """
    Return (item, semantic_score) pairs ordered by cosine similarity desc.
    Only items that have an embedding and are active are considered.
    """
    distance_col = CatalogItem.embedding.cosine_distance(query_embedding)
    where_clauses = [
        CatalogItem.workspace_id == workspace_id,
        CatalogItem.status == "active",
        CatalogItem.embedding.isnot(None),
    ]
    cat_filter = _category_filter(allowed_category_ids)
    if cat_filter is not None:
        where_clauses.append(cat_filter)
    rows = db.execute(
        select(CatalogItem, distance_col.label("distance"))
        .where(*where_clauses)
        .order_by(distance_col.asc())
        .limit(top_k)
    ).all()
    return [(row.CatalogItem, float(1.0 - row.distance)) for row in rows]


def _fetch_active_catalog_items(
    db: Session,
    workspace_id: uuid.UUID,
    allowed_category_ids: list[uuid.UUID] | None = None,
) -> list[CatalogItem]:
    """All active items in scope — used by Camada 1 (full injection)."""
    where_clauses = [CatalogItem.workspace_id == workspace_id, CatalogItem.status == "active"]
    cat_filter = _category_filter(allowed_category_ids)
    if cat_filter is not None:
        where_clauses.append(cat_filter)
    return list(db.scalars(select(CatalogItem).where(*where_clauses)).all())


def _full_catalog_fits_budget(items: list[CatalogItem]) -> bool:
    """
    catalog-retrieval-robustness-prd.md — Camada 1 eligibility check. Adapts
    to both axes that make a catalog "small" in the sense that matters here:
    few items, AND/OR short descriptions. A catalog with 30 one-line items
    can fit; one with 8 long, detailed items might not — both are correctly
    routed by summing actual content length instead of just counting items.
    """
    total = sum(
        len(item.name or "") + len(item.short_description or "") + _ITEM_FORMAT_OVERHEAD_CHARS
        for item in items
    )
    return total <= _FULL_CATALOG_CHAR_BUDGET


def _rrf_combine(*ranked_id_lists: list[uuid.UUID]) -> dict[uuid.UUID, float]:
    """
    Reciprocal Rank Fusion — combines multiple ranked lists into one score
    per id: score = Σ 1/(k + rank) across every list the id appears in
    (1-indexed rank). k=60 is the standard from the original RRF paper.

    Used instead of a weighted sum of raw scores (the old 0.7*semantic +
    0.3*lexical) because it only cares about *relative* ordering within each
    method — it doesn't break when one method's score distribution shifts
    (e.g. a catalog with unusually short/similar descriptions compressing
    semantic scores into a narrow band), which a fixed-weight raw-score sum
    is very sensitive to.
    """
    scores: dict[uuid.UUID, float] = {}
    for ranked_ids in ranked_id_lists:
        for rank, item_id in enumerate(ranked_ids, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (_RRF_K + rank)
    return scores


@dataclass
class _RetrievalOutcome:
    items: list[CatalogRetrievalItem]
    # True when Tier 2 found candidates but none cleared the confidence
    # floor — distinct from "found literally nothing", which needs no hedge
    # (see retrieve_catalog_context's use of this flag).
    had_weak_candidates: bool = False


def _retrieve_catalog_items_full(
    db: Session,
    workspace_id: uuid.UUID,
    query: str,
    limit: int = _DEFAULT_LIMIT,
    provider: EmbeddingProvider | None = None,
    allowed_category_ids: list[uuid.UUID] | None = None,
) -> _RetrievalOutcome:
    """
    catalog-retrieval-robustness-prd.md — the confidence-aware implementation
    behind both retrieve_catalog_items() (backward-compatible wrapper, plain
    list return) and retrieve_catalog_context() (uses had_weak_candidates to
    decide whether to inject an explicit "inconclusive" warning).

    Strategy
    --------
    Camada 1 — if the workspace's active (in-scope) catalog is small enough
    to fit _FULL_CATALOG_CHAR_BUDGET, skip ranking entirely and return every
    item. Zero risk of a real match scoring too low to surface.

    Camada 2 — otherwise, real retrieval:
      a. Semantic search via pgvector cosine similarity.
      b. Native Postgres full-text search (replaces the old ILIKE scan).
      c. Combine via Reciprocal Rank Fusion.
      d. Drop any candidate that doesn't clear the confidence floor (decent
         semantic similarity OR a genuine full-text match) — never surface
         a "least bad of the bunch" result as if it were reliable.
      e. If embedding fails entirely, fall back to full-text search alone.

    Workspace isolation is enforced at every query.
    """
    limit = min(limit, _MAX_LIMIT)
    terms = _extract_terms(query)

    if not terms and not query.strip():
        return _RetrievalOutcome(items=[])

    # ── Camada 1 ───────────────────────────────────────────────────────────
    full_items = _fetch_active_catalog_items(db, workspace_id, allowed_category_ids)
    if full_items and _full_catalog_fits_budget(full_items):
        cat_map, primary_media_ids = _resolve_support_data(db, workspace_id, full_items)
        return _RetrievalOutcome(items=[
            _to_retrieval_item(
                item, cat_map, primary_media_ids, score=1.0, retrieval_method="full_catalog",
            )
            for item in full_items
        ])

    # ── Camada 2 — hybrid (semantic + full-text, combined via RRF) ─────────
    try:
        from app.services.embedding_service import embed_texts

        embed_result = embed_texts([query.strip()], provider=provider)
        query_embedding = embed_result.embeddings[0]

        sem_rows = _semantic_search(
            db, workspace_id, query_embedding, top_k=limit * 3,
            allowed_category_ids=allowed_category_ids,
        )
        fts_rows = _fulltext_search(
            db, workspace_id, query, over_fetch=limit * 5,
            allowed_category_ids=allowed_category_ids,
        )

        if sem_rows or fts_rows:
            all_items: dict[uuid.UUID, CatalogItem] = {r.id: r for r, _ in sem_rows}
            for r, _ in fts_rows:
                all_items.setdefault(r.id, r)

            sem_scores = {r.id: s for r, s in sem_rows}
            fts_scores = {r.id: s for r, s in fts_rows}
            fts_ids = {r.id for r, _ in fts_rows}
            rrf_scores = _rrf_combine(
                [r.id for r, _ in sem_rows], [r.id for r, _ in fts_rows],
            )

            passing: list[tuple[CatalogItem, float, float, float]] = []
            for item in all_items.values():
                sem = sem_scores.get(item.id, 0.0)
                fts = fts_scores.get(item.id, 0.0)
                if sem < _SEMANTIC_CONFIDENCE_FLOOR and item.id not in fts_ids:
                    continue  # confidence floor — see _SEMANTIC_CONFIDENCE_FLOOR docstring above
                passing.append((item, rrf_scores.get(item.id, 0.0), sem, fts))

            if not passing:
                # Had candidates, none confident enough — caller injects an
                # honest "search was inconclusive" note instead of silence.
                return _RetrievalOutcome(items=[], had_weak_candidates=bool(all_items))

            passing.sort(key=lambda x: x[1], reverse=True)
            top = passing[:limit]

            all_rows = [c[0] for c in passing]
            cat_map, primary_media_ids = _resolve_support_data(db, workspace_id, all_rows)

            return _RetrievalOutcome(items=[
                _to_retrieval_item(
                    item, cat_map, primary_media_ids,
                    score=round(final, 4),
                    semantic_score=round(sem, 4),
                    lexical_score=round(fts, 4),
                    retrieval_method="hybrid",
                )
                for item, final, sem, fts in top
            ])

    except (EmbeddingError, Exception):  # noqa: BLE001
        # Embedding failed or provider not configured — fall through to full-text-only.
        pass

    # ── Full-text-only fallback (embedding unavailable) ─────────────────────
    if not terms:
        return _RetrievalOutcome(items=[])

    fts_rows = _fulltext_search(
        db, workspace_id, query, over_fetch=limit * 5,
        allowed_category_ids=allowed_category_ids,
    )
    if not fts_rows:
        return _RetrievalOutcome(items=[])

    rows = [r for r, _ in fts_rows]
    scores = {r.id: s for r, s in fts_rows}
    cat_map, primary_media_ids = _resolve_support_data(db, workspace_id, rows)

    return _RetrievalOutcome(items=[
        _to_retrieval_item(
            item, cat_map, primary_media_ids,
            score=round(scores[item.id], 4),
            lexical_score=round(scores[item.id], 4),
            retrieval_method="lexical_fallback",
        )
        for item in rows[:limit]
    ])


def retrieve_catalog_items(
    db: Session,
    workspace_id: uuid.UUID,
    query: str,
    limit: int = _DEFAULT_LIMIT,
    provider: EmbeddingProvider | None = None,
    allowed_category_ids: list[uuid.UUID] | None = None,
) -> list[CatalogRetrievalItem]:
    """
    Return up to *limit* active catalog items relevant to *query*.

    Backward-compatible wrapper around _retrieve_catalog_items_full — plain
    list return, same signature as before catalog-retrieval-robustness-prd.md.
    retrieve_catalog_context() (the real production entry point) calls the
    richer variant directly to also get the had_weak_candidates signal.
    """
    return _retrieve_catalog_items_full(
        db, workspace_id, query, limit=limit, provider=provider,
        allowed_category_ids=allowed_category_ids,
    ).items


# ── Context block builder ─────────────────────────────────────────────────────

_CATALOG_DIVIDER = "──────────────────────────────────────────────────────"

_CATALOG_HEADER = """\
CATÁLOGO RELEVANTE:
Use apenas os itens abaixo para falar sobre produtos, serviços, planos ou ofertas.
Não invente itens, preços, disponibilidade ou características que não estejam listadas."""

_CATALOG_RULES = """\
Regras obrigatórias ao responder com base no Catálogo:
- Recomende no máximo 3 opções por resposta.
- Explique por que cada opção combina com o pedido do cliente.
- Se o cliente pedir algo que não existe no Catálogo, diga que não encontrou essa \
opção cadastrada.
- Não invente preço, disponibilidade ou características.
- Se um item não tiver preço cadastrado, informe que o preço não está disponível \
e ofereça chamar a equipe.
- Se precisar de simulação, negociação, agendamento ou confirmação, ofereça acionar \
um humano da equipe."""

# catalog-retrieval-robustness-prd.md — shown instead of a normal catalog
# block when the search had candidates but none cleared the confidence
# floor (never shown for "genuinely found nothing", see had_weak_candidates
# in retrieve_catalog_context). Found via a real production incident: the
# model received a weak top-3 with no confidence signal and confidently
# told the customer an item "was no longer in the catalog" — false.
_CATALOG_INCONCLUSIVE_BLOCK = """\
CATÁLOGO: a busca não encontrou nenhum item claramente relevante para essa pergunta.
Isso pode ser uma limitação da busca, não uma confirmação de que o item não existe \
ou não está disponível. Não afirme que um produto/serviço não existe ou "não está \
mais no catálogo" com base só nisso — peça mais detalhes ao cliente sobre o que ele \
procura, ou ofereça verificar com a equipe antes de descartar a opção."""


def _format_price(price: float | None, currency: str) -> str:
    if price is None:
        return "Não informado"
    try:
        return f"R$ {price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"{currency} {price}"


def _format_metadata(metadata: dict) -> str | None:
    if not metadata:
        return None
    parts = [f"{k}={v}" for k, v in list(metadata.items())[:8]]
    return ", ".join(parts)


def build_catalog_context_block(items: list[CatalogRetrievalItem]) -> str:
    """
    Build the catalog context block to inject into the system prompt.

    Returns a multi-line string following the same structural conventions as
    build_rag_context_block() in agent_context_builder.py.
    """
    lines: list[str] = [_CATALOG_HEADER, _CATALOG_DIVIDER]

    for i, item in enumerate(items, start=1):
        entry: list[str] = [f"{i}. Nome: {item.name}"]

        if item.category_name:
            entry.append(f"   Categoria: {item.category_name}")

        entry.append(f"   Preço: {_format_price(item.price, item.currency)}")

        if item.short_description:
            entry.append(f"   Descrição: {item.short_description}")

        if item.tags:
            entry.append(f"   Tags: {', '.join(item.tags)}")

        meta_str = _format_metadata(item.metadata_json)
        if meta_str:
            entry.append(f"   Atributos: {meta_str}")

        media_status = "disponível" if item.primary_media_available else "não disponível"
        entry.append(f"   Mídia principal: {media_status}")

        lines.append("\n".join(entry))

    lines.append(_CATALOG_DIVIDER)
    lines.append(_CATALOG_RULES)

    return "\n\n".join(lines)


# ── Main entry point ──────────────────────────────────────────────────────────

def retrieve_catalog_context(
    db: Session,
    workspace_id: uuid.UUID,
    query: str,
    limit: int = _DEFAULT_LIMIT,
    allowed_category_ids: list[uuid.UUID] | None = None,
) -> CatalogRetrievalResult:
    """
    Full pipeline: intent detection → retrieval → context block.

    Never raises. All errors are captured in result.error_message so callers
    can degrade gracefully (same pattern as knowledge_retrieval_service).

    Returns
    -------
    CatalogRetrievalResult with:
      - items: list of matched items (empty if no intent or no matches)
      - context_block: formatted string for prompt injection, or None
      - retrieval_attempted: True if intent was detected and DB queried
      - error_message: non-None only if an exception occurred
    """
    result = CatalogRetrievalResult(query=query)

    if not query or not query.strip():
        return result

    if not should_retrieve_catalog(query):
        return result

    result.retrieval_attempted = True

    try:
        outcome = _retrieve_catalog_items_full(
            db, workspace_id, query, limit=limit,
            allowed_category_ids=allowed_category_ids,
        )
        result.items = outcome.items
        if outcome.items:
            result.context_block = build_catalog_context_block(outcome.items)
        elif outcome.had_weak_candidates:
            result.context_block = _CATALOG_INCONCLUSIVE_BLOCK
    except Exception as exc:  # noqa: BLE001
        logger.warning("catalog_retrieval_error workspace=%s error=%s", workspace_id, exc)
        result.error_message = f"Catalog retrieval error: {str(exc)[:200]}"

    return result
