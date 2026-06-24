"use client";

import type { ConversationMessage } from "@/lib/api";

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function senderLabel(msg: ConversationMessage, contactName: string | null): string {
  if (msg.direction === "inbound")  return contactName ?? "Cliente";
  if (msg.direction === "outbound") return msg.sender_type === "agent" ? "Agente" : "Humano";
  return msg.sender_type === "system" ? "Sistema" : "Nota interna";
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

function OutboundBubble({ msg, contactName }: { msg: ConversationMessage; contactName: string | null }) {
  const isAgent = msg.sender_type === "agent";
  return (
    <div className="flex items-end gap-2 max-w-[75%] self-end flex-row-reverse">
      <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mb-0.5 ${isAgent ? "bg-nb-primary-bg border border-nb-primary/20" : "bg-nb-soft border border-nb-border"}`}>
        <span className="text-[10px] font-medium text-nb-secondary">{isAgent ? "A" : "H"}</span>
      </div>
      <div className="flex flex-col gap-0.5 items-end">
        <span className="text-[10px] text-nb-muted px-1">{senderLabel(msg, contactName)}</span>
        <div className={`rounded-2xl rounded-br-sm px-4 py-2.5 text-sm break-words whitespace-pre-wrap text-white ${isAgent ? "bg-nb-primary-strong" : "bg-nb-primary"}`}>
          {msg.content}
        </div>
        <span className="text-[10px] text-nb-muted/50 px-1">{formatTimestamp(msg.created_at)}</span>
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

export function MessageBubble({ msg, contactName }: { msg: ConversationMessage; contactName: string | null }) {
  if (msg.direction === "inbound")  return <InboundBubble  msg={msg} contactName={contactName} />;
  if (msg.direction === "outbound") return <OutboundBubble msg={msg} contactName={contactName} />;
  return <InternalBubble msg={msg} contactName={contactName} />;
}
