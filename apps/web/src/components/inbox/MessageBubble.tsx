"use client";

import { useState } from "react";
import { AlertTriangle, BookOpen, ChevronDown, ChevronUp, ImageOff, Loader2, RotateCcw } from "lucide-react";
import type { CatalogMediaDelivery, CatalogRetrieval, CatalogRetrievalItem, ConversationMessage, MessageDelivery } from "@/lib/api";
import { api } from "@/lib/api";

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function senderLabel(msg: ConversationMessage, contactName: string | null): string {
  if (msg.direction === "inbound")  return contactName ?? "Cliente";
  if (msg.direction === "outbound") return msg.sender_type === "agent" ? "Agente" : "Humano";
  return msg.sender_type === "system" ? "Sistema" : "Nota interna";
}

function getDelivery(msg: ConversationMessage): MessageDelivery | null {
  return (msg.metadata_json?.delivery as MessageDelivery) ?? null;
}

function getCatalogMediaDelivery(msg: ConversationMessage): CatalogMediaDelivery | null {
  const raw = msg.metadata_json?.catalog_media_delivery;
  if (!raw || typeof raw !== "object") return null;
  return raw as CatalogMediaDelivery;
}

function getCatalogRetrieval(msg: ConversationMessage): CatalogRetrieval | null {
  const raw = msg.metadata_json?.catalog_retrieval;
  if (!raw || typeof raw !== "object") return null;
  return raw as CatalogRetrieval;
}

function scoreLabel(item: CatalogRetrievalItem): string {
  if (item.score != null) return item.score.toFixed(2);
  return "—";
}

function methodLabel(method: string | undefined): string {
  if (method === "hybrid") return "híbrido";
  if (method === "lexical_fallback") return "lexical";
  if (method === "semantic") return "semântico";
  if (method === "lexical") return "lexical";
  return method ?? "—";
}

function CatalogRetrievalBadge({ msg }: { msg: ConversationMessage }) {
  const [open, setOpen] = useState(false);
  const retrieval = getCatalogRetrieval(msg);
  if (!retrieval) return null;

  const items = Array.isArray(retrieval.items_considered) ? retrieval.items_considered : [];
  const count = items.length;
  const label = count === 0
    ? "Catálogo consultado · sem itens"
    : count === 1
    ? "Catálogo consultado · 1 item"
    : `Catálogo consultado · ${count} itens`;

  return (
    <div className="mt-1 w-full max-w-full">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-[10px] text-nb-muted/70 hover:text-nb-muted transition-colors"
      >
        <BookOpen className="w-3 h-3 flex-shrink-0" />
        <span>{label}</span>
        {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>

      {open && (
        <div className="mt-1.5 rounded-xl border border-nb-border bg-nb-bg px-3 py-2.5 space-y-2 text-[11px] text-nb-secondary">
          {retrieval.query && (
            <p className="text-nb-muted italic break-words">
              Consulta: &ldquo;{retrieval.query}&rdquo;
            </p>
          )}
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-nb-muted">
            {retrieval.retrieval_method && (
              <span>Método: <span className="text-nb-secondary">{methodLabel(retrieval.retrieval_method)}</span></span>
            )}
            {retrieval.embedding_used != null && (
              <span>Embedding: <span className="text-nb-secondary">{retrieval.embedding_used ? "usado" : "não usado"}</span></span>
            )}
          </div>

          {count === 0 ? (
            <p className="text-nb-muted">Nenhum item relevante encontrado.</p>
          ) : (
            <ol className="space-y-1.5">
              {items.map((item, idx) => (
                <li key={item.id ?? idx} className="space-y-0.5">
                  <p className="font-medium text-nb-text">{idx + 1}. {item.name ?? "Item sem nome"}</p>
                  <div className="flex flex-wrap gap-x-3 text-nb-muted">
                    <span>Score: <span className="text-nb-secondary">{scoreLabel(item)}</span></span>
                    {item.semantic_score != null && (
                      <span>Semântico: <span className="text-nb-secondary">{item.semantic_score.toFixed(2)}</span></span>
                    )}
                    {item.lexical_score != null && (
                      <span>Lexical: <span className="text-nb-secondary">{item.lexical_score.toFixed(2)}</span></span>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}

function CatalogMediaMessageCard({ delivery }: { delivery: CatalogMediaDelivery }) {
  const [imageFailed, setImageFailed] = useState(false);
  const itemName = typeof delivery.item_name === "string" ? delivery.item_name : null;
  const caption = typeof delivery.caption === "string" ? delivery.caption : null;
  const mediaUrl = typeof delivery.media_url === "string" ? delivery.media_url : null;
  const sent = delivery.sent === true;
  const failed = delivery.sent === false;
  const showImage = !!mediaUrl && !imageFailed;

  return (
    <div className="w-56 rounded-2xl rounded-br-sm overflow-hidden bg-nb-elevated border border-nb-border text-nb-text">
      <div className="aspect-square w-full bg-nb-bg flex items-center justify-center overflow-hidden">
        {showImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={mediaUrl}
            alt={itemName ?? "Imagem do Catálogo"}
            className="w-full h-full object-cover"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className="flex flex-col items-center gap-1.5 text-nb-muted">
            <ImageOff className="w-6 h-6" />
            <span className="text-[10px]">Prévia indisponível</span>
          </div>
        )}
      </div>
      <div className="px-3 py-2.5 space-y-1">
        <p className="text-[10px] uppercase tracking-wide text-nb-muted/70">Imagem do Catálogo</p>
        {itemName && <p className="text-sm font-medium text-nb-text break-words">{itemName}</p>}
        {caption && caption !== itemName && (
          <p className="text-xs text-nb-secondary break-words">{caption}</p>
        )}
        {failed ? (
          <div className="flex items-start gap-1 text-[10px] text-nb-danger pt-0.5">
            <AlertTriangle className="w-3 h-3 flex-shrink-0 mt-px" />
            <span>
              Falha ao enviar imagem do Catálogo
              {typeof delivery.error === "string" && delivery.error ? `: ${delivery.error}` : ""}
            </span>
          </div>
        ) : sent ? (
          <p className="text-[10px] text-nb-muted/70 pt-0.5">Enviada</p>
        ) : null}
      </div>
    </div>
  );
}

function deliveryErrorHint(delivery: MessageDelivery): string {
  if (delivery.error_status === 401) return "Token do WhatsApp inválido ou expirado.";
  if (delivery.error_status === 400) return "A Meta recusou a mensagem. Verifique o número ou a janela de atendimento.";
  return "Falha ao enviar pelo WhatsApp.";
}

function DeliveryBadge({
  msg,
  onRetried,
}: {
  msg: ConversationMessage;
  onRetried: (updated: ConversationMessage) => void;
}) {
  const delivery = getDelivery(msg);
  if (!delivery || delivery.channel !== "whatsapp") return null;

  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);

  if (delivery.status === "failed") {
    const hint = deliveryErrorHint(delivery);

    async function handleRetry() {
      setRetryError(null);
      setRetrying(true);
      try {
        const updated = await api.conversations.messages.retryDelivery(
          msg.conversation_id,
          msg.id,
        );
        onRetried(updated);
      } catch {
        setRetryError("Não foi possível reenviar.");
      } finally {
        setRetrying(false);
      }
    }

    return (
      <div className="flex flex-col items-end gap-1 mt-0.5">
        <div className="flex items-center gap-1 text-[10px] text-nb-danger">
          <AlertTriangle className="w-3 h-3 flex-shrink-0" />
          <span>Não entregue</span>
        </div>
        <p className="text-[10px] text-nb-muted/70">{hint}</p>
        <button
          type="button"
          onClick={handleRetry}
          disabled={retrying}
          className="flex items-center gap-1 text-[10px] text-nb-primary hover:text-nb-primary-strong transition-colors disabled:opacity-50"
        >
          {retrying ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <RotateCcw className="w-3 h-3" />
          )}
          {retrying ? "Reenviando…" : "Tentar novamente"}
        </button>
        {retryError && (
          <p className="text-[10px] text-nb-danger">{retryError}</p>
        )}
      </div>
    );
  }

  return null;
}

function InboundBubble({ msg, contactName }: { msg: ConversationMessage; contactName: string | null }) {
  return (
    <div className="flex items-end gap-2 max-w-[75%]">
      <div className="w-6 h-6 rounded-full bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0 mb-0.5">
        <span className="text-[10px] text-nb-muted font-medium">
          {(contactName ?? "C")[0].toUpperCase()}
        </span>
      </div>
      <div className="flex flex-col gap-0.5">
        <span className="text-[10px] text-nb-muted px-1">{senderLabel(msg, contactName)}</span>
        <div className="bg-nb-elevated text-nb-text rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm break-words whitespace-pre-wrap">
          {msg.content}
        </div>
        <span className="text-[10px] text-nb-muted/50 px-1">{formatTimestamp(msg.created_at)}</span>
      </div>
    </div>
  );
}

function OutboundBubble({
  msg,
  contactName,
  onMessageUpdated,
}: {
  msg: ConversationMessage;
  contactName: string | null;
  onMessageUpdated: (updated: ConversationMessage) => void;
}) {
  const isAgent = msg.sender_type === "agent";
  const catalogMedia = getCatalogMediaDelivery(msg);
  return (
    <div className="flex items-end gap-2 max-w-[75%] self-end flex-row-reverse">
      <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mb-0.5 ${isAgent ? "bg-nb-primary-bg border border-nb-primary/20" : "bg-nb-soft border border-nb-border"}`}>
        <span className="text-[10px] font-medium text-nb-secondary">{isAgent ? "A" : "H"}</span>
      </div>
      <div className="flex flex-col gap-0.5 items-end">
        <span className="text-[10px] text-nb-muted px-1">{senderLabel(msg, contactName)}</span>
        {catalogMedia ? (
          <CatalogMediaMessageCard delivery={catalogMedia} />
        ) : (
          <div className={`rounded-2xl rounded-br-sm px-4 py-2.5 text-sm break-words whitespace-pre-wrap text-white ${isAgent ? "bg-nb-primary-strong" : "bg-nb-primary"}`}>
            {msg.content}
          </div>
        )}
        <span className="text-[10px] text-nb-muted/50 px-1">{formatTimestamp(msg.created_at)}</span>
        <DeliveryBadge msg={msg} onRetried={onMessageUpdated} />
        {isAgent && <CatalogRetrievalBadge msg={msg} />}
      </div>
    </div>
  );
}

function InternalBubble({ msg, contactName }: { msg: ConversationMessage; contactName: string | null }) {
  return (
    <div className="flex justify-center">
      <div className="flex flex-col items-center gap-1 max-w-[80%]">
        <div className="flex items-center gap-1.5">
          <div className="h-px w-8 bg-nb-border" />
          <span className="text-[10px] text-nb-muted font-medium uppercase tracking-wide">
            {senderLabel(msg, contactName)}
          </span>
          <div className="h-px w-8 bg-nb-border" />
        </div>
        <div className="border border-dashed border-nb-border rounded-xl px-3 py-2 text-xs text-nb-muted text-center break-words whitespace-pre-wrap">
          {msg.content}
        </div>
        <span className="text-[10px] text-nb-muted/50">{formatTimestamp(msg.created_at)}</span>
      </div>
    </div>
  );
}

export function MessageBubble({
  msg,
  contactName,
  onMessageUpdated,
}: {
  msg: ConversationMessage;
  contactName: string | null;
  onMessageUpdated?: (updated: ConversationMessage) => void;
}) {
  const noop = (_: ConversationMessage) => {};
  if (msg.direction === "inbound")  return <InboundBubble  msg={msg} contactName={contactName} />;
  if (msg.direction === "outbound") return <OutboundBubble msg={msg} contactName={contactName} onMessageUpdated={onMessageUpdated ?? noop} />;
  return <InternalBubble msg={msg} contactName={contactName} />;
}
