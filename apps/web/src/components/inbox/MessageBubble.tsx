"use client";

import type { ConversationMessage } from "@/lib/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function senderLabel(msg: ConversationMessage, contactName: string | null): string {
  if (msg.direction === "inbound") return contactName ?? "Cliente";
  if (msg.direction === "outbound") {
    return msg.sender_type === "agent" ? "Agente" : "Humano";
  }
  // internal
  return msg.sender_type === "system" ? "Sistema" : "Nota interna";
}

// ── Inbound (customer → left) ─────────────────────────────────────────────────

function InboundBubble({
  msg,
  contactName,
}: {
  msg: ConversationMessage;
  contactName: string | null;
}) {
  return (
    <div className="flex items-end gap-2 max-w-[75%]">
      {/* Avatar placeholder */}
      <div className="w-6 h-6 rounded-full bg-gray-700 flex items-center justify-center flex-shrink-0 mb-0.5">
        <span className="text-[10px] text-gray-400 font-medium">
          {(contactName ?? "C")[0].toUpperCase()}
        </span>
      </div>

      <div className="flex flex-col gap-0.5">
        <span className="text-[10px] text-gray-500 px-1">
          {senderLabel(msg, contactName)}
        </span>
        <div className="bg-gray-700 text-gray-100 rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm break-words whitespace-pre-wrap">
          {msg.content}
        </div>
        <span className="text-[10px] text-gray-600 px-1">
          {formatTimestamp(msg.created_at)}
        </span>
      </div>
    </div>
  );
}

// ── Outbound (human/agent → right) ────────────────────────────────────────────

function OutboundBubble({
  msg,
  contactName,
}: {
  msg: ConversationMessage;
  contactName: string | null;
}) {
  const isAgent = msg.sender_type === "agent";

  return (
    <div className="flex items-end gap-2 max-w-[75%] self-end flex-row-reverse">
      {/* Avatar placeholder */}
      <div
        className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mb-0.5 ${
          isAgent ? "bg-indigo-600/30" : "bg-gray-600"
        }`}
      >
        <span className="text-[10px] text-gray-300 font-medium">
          {isAgent ? "A" : "H"}
        </span>
      </div>

      <div className="flex flex-col gap-0.5 items-end">
        <span className="text-[10px] text-gray-500 px-1">
          {senderLabel(msg, contactName)}
        </span>
        <div
          className={`rounded-2xl rounded-br-sm px-4 py-2.5 text-sm break-words whitespace-pre-wrap text-white ${
            isAgent ? "bg-indigo-700" : "bg-indigo-600"
          }`}
        >
          {msg.content}
        </div>
        <span className="text-[10px] text-gray-600 px-1">
          {formatTimestamp(msg.created_at)}
        </span>
      </div>
    </div>
  );
}

// ── Internal (system/note → center) ───────────────────────────────────────────

function InternalBubble({
  msg,
  contactName,
}: {
  msg: ConversationMessage;
  contactName: string | null;
}) {
  return (
    <div className="flex justify-center">
      <div className="flex flex-col items-center gap-1 max-w-[80%]">
        <div className="flex items-center gap-1.5">
          <div className="h-px w-8 bg-gray-700" />
          <span className="text-[10px] text-gray-600 font-medium uppercase tracking-wide">
            {senderLabel(msg, contactName)}
          </span>
          <div className="h-px w-8 bg-gray-700" />
        </div>
        <div className="border border-dashed border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-400 text-center break-words whitespace-pre-wrap">
          {msg.content}
        </div>
        <span className="text-[10px] text-gray-600">
          {formatTimestamp(msg.created_at)}
        </span>
      </div>
    </div>
  );
}

// ── Export ────────────────────────────────────────────────────────────────────

export function MessageBubble({
  msg,
  contactName,
}: {
  msg: ConversationMessage;
  contactName: string | null;
}) {
  if (msg.direction === "inbound")  return <InboundBubble  msg={msg} contactName={contactName} />;
  if (msg.direction === "outbound") return <OutboundBubble msg={msg} contactName={contactName} />;
  return <InternalBubble msg={msg} contactName={contactName} />;
}
