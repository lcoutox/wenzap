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

from sqlalchemy import or_, select
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
_MAX_LIMIT = 5
_MIN_TERM_LENGTH = 2
_SEMANTIC_WEIGHT = 0.7
_LEXICAL_WEIGHT = 0.3

# Numeric values that look like prices ("90 mil", "89500", "88.900").
_PRICE_PATTERN = re.compile(r"(\d[\d.,]*)\s*(mil|k)?", re.IGNORECASE)


def _extract_terms(query: str) -> list[str]:
    """Tokenise the query into searchable terms, filtering short stop-words."""
    cleaned = re.sub(r"[!?;:()\[\]\"'`]", " ", query.lower())
    tokens = cleaned.split()
    return [t for t in tokens if len(t) >= _MIN_TERM_LENGTH]


def _lexical_score(item: CatalogItem, terms: list[str]) -> float:
    """Return number of query terms that appear in the item's searchable content."""
    haystack = " ".join(filter(None, [
        item.searchable_text or "",
        item.name or "",
        (item.short_description or "").lower(),
        (item.description or "")[:300].lower(),
        " ".join(item.tags or []).lower(),
    ])).lower()
    return sum(1.0 for t in terms if t in haystack)


def _normalise_lexical(raw: float, max_terms: int) -> float:
    """Map raw term-count score to [0, 1] range."""
    if max_terms <= 0:
        return 0.0
    return min(raw / max_terms, 1.0)


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


def _lexical_search(
    db: Session,
    workspace_id: uuid.UUID,
    terms: list[str],
    over_fetch: int,
    allowed_category_ids: list[uuid.UUID] | None = None,
) -> list[CatalogItem]:
    """Return active items that match any query term via ILIKE."""
    if not terms:
        return []
    conditions = []
    for term in terms:
        like = f"%{term}%"
        conditions.append(or_(
            CatalogItem.searchable_text.ilike(like),
            CatalogItem.name.ilike(like),
            CatalogItem.short_description.ilike(like),
            CatalogItem.description.ilike(like),
        ))
    where_clauses = [
        CatalogItem.workspace_id == workspace_id,
        CatalogItem.status == "active",
        or_(*conditions),
    ]
    cat_filter = _category_filter(allowed_category_ids)
    if cat_filter is not None:
        where_clauses.append(cat_filter)
    return list(db.scalars(
        select(CatalogItem).where(*where_clauses).limit(over_fetch)
    ).all())


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

    Strategy
    --------
    1. If the workspace has embedded items, attempt hybrid search:
       a. Embed the query using the configured provider.
       b. Semantic search via pgvector cosine distance.
       c. Lexical search via ILIKE for complementary coverage.
       d. Merge: final_score = 0.7 * semantic + 0.3 * lexical.
    2. If embedding fails or no items have embeddings, fall back to
       pure lexical search (Catálogo.3 behaviour).

    Workspace isolation is enforced at every query.
    """
    limit = min(limit, _MAX_LIMIT)
    terms = _extract_terms(query)

    if not terms and not query.strip():
        return []

    # ── Attempt semantic (hybrid) retrieval ───────────────────────────────────
    try:
        from app.services.embedding_service import embed_texts

        embed_result = embed_texts([query.strip()], provider=provider)
        query_embedding = embed_result.embeddings[0]

        sem_rows = _semantic_search(
            db, workspace_id, query_embedding, top_k=limit * 3,
            allowed_category_ids=allowed_category_ids,
        )

        if sem_rows:
            # Fetch lexical candidates for the same workspace to compute lexical score.
            lex_rows = _lexical_search(
                db, workspace_id, terms, over_fetch=limit * 5,
                allowed_category_ids=allowed_category_ids,
            )

            # Merge: all semantically-found items + lexical-only items.
            all_items: dict[uuid.UUID, CatalogItem] = {r.id: r for r, _ in sem_rows}
            for r in lex_rows:
                all_items.setdefault(r.id, r)

            sem_scores = {r.id: s for r, s in sem_rows}

            # Score each candidate.
            candidates: list[tuple[CatalogItem, float, float, float]] = []
            max_terms = max(len(terms), 1)
            for item in all_items.values():
                sem = sem_scores.get(item.id, 0.0)
                raw_lex = _lexical_score(item, terms) if terms else 0.0
                lex = _normalise_lexical(raw_lex, max_terms)
                final = _SEMANTIC_WEIGHT * sem + _LEXICAL_WEIGHT * lex
                if final > 0:
                    candidates.append((item, final, sem, lex))

            candidates.sort(key=lambda x: x[1], reverse=True)
            top = candidates[:limit]

            if not top:
                return []

            all_rows = [c[0] for c in candidates]
            cat_map, primary_media_ids = _resolve_support_data(db, workspace_id, all_rows)

            return [
                _to_retrieval_item(
                    item, cat_map, primary_media_ids,
                    score=round(final, 4),
                    semantic_score=round(sem, 4),
                    lexical_score=round(lex, 4),
                    retrieval_method="hybrid",
                )
                for item, final, sem, lex in top
            ]

    except (EmbeddingError, Exception):  # noqa: BLE001
        # Embedding failed or provider not configured — fall through to lexical.
        pass

    # ── Lexical fallback ──────────────────────────────────────────────────────
    if not terms:
        return []

    rows = _lexical_search(
        db, workspace_id, terms, over_fetch=limit * 5,
        allowed_category_ids=allowed_category_ids,
    )
    if not rows:
        return []

    cat_map, primary_media_ids = _resolve_support_data(db, workspace_id, rows)
    max_terms = max(len(terms), 1)

    scored = [(item, _lexical_score(item, terms)) for item in rows]
    scored = [(i, s) for i, s in scored if s > 0]
    scored.sort(key=lambda x: x[1], reverse=True)

    return [
        _to_retrieval_item(
            item, cat_map, primary_media_ids,
            score=round(_normalise_lexical(raw, max_terms), 4),
            lexical_score=round(_normalise_lexical(raw, max_terms), 4),
            retrieval_method="lexical_fallback",
        )
        for item, raw in scored[:limit]
    ]


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
        items = retrieve_catalog_items(
            db, workspace_id, query, limit=limit,
            allowed_category_ids=allowed_category_ids,
        )
        result.items = items
        if items:
            result.context_block = build_catalog_context_block(items)
    except Exception as exc:  # noqa: BLE001
        logger.warning("catalog_retrieval_error workspace=%s error=%s", workspace_id, exc)
        result.error_message = f"Catalog retrieval error: {str(exc)[:200]}"

    return result
