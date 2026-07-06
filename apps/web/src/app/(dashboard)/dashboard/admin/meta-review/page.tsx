"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { MetaReviewConversation, MetaReviewMessage, MetaReviewTemplate } from "@/lib/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function formatDate(iso: string) {
  const d = new Date(iso);
  const today = new Date();
  if (d.toDateString() === today.toDateString()) return "Hoje";
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

function contactName(conv: MetaReviewConversation) {
  return conv.contact?.profile_name || conv.contact?.phone_e164 || "Desconhecido";
}

// ── Conversation item (left panel) ────────────────────────────────────────────

function ConversationItem({
  conv,
  selected,
  onClick,
}: {
  conv: MetaReviewConversation;
  selected: boolean;
  onClick: () => void;
}) {
  const preview = conv.last_message?.body ?? "";
  const time = conv.last_message ? formatDate(conv.last_message.created_at) : "";
  const isOutbound = conv.last_message?.direction === "outbound";

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3 flex items-start gap-3 border-b border-nb-border transition-colors ${
        selected ? "bg-nb-elevated" : "hover:bg-nb-elevated/50"
      }`}
    >
      <div className="w-9 h-9 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
        <span className="text-green-700 text-sm font-semibold">
          {contactName(conv).charAt(0).toUpperCase()}
        </span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium text-nb-primary truncate">{contactName(conv)}</span>
          <span className="text-xs text-nb-muted flex-shrink-0">{time}</span>
        </div>
        <p className="text-xs text-nb-muted truncate mt-0.5">
          {isOutbound && <span className="text-nb-muted">Você: </span>}
          {preview || <span className="italic">Sem mensagens</span>}
        </p>
      </div>
    </button>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────

function Bubble({ msg }: { msg: MetaReviewMessage }) {
  const isOut = msg.direction === "outbound";
  return (
    <div className={`flex ${isOut ? "justify-end" : "justify-start"} mb-1`}>
      <div
        className={`max-w-[72%] rounded-2xl px-3.5 py-2 text-sm ${
          isOut
            ? "bg-green-500 text-white rounded-br-sm"
            : "bg-nb-panel border border-nb-border text-nb-primary rounded-bl-sm"
        }`}
      >
        <p className="leading-relaxed whitespace-pre-wrap break-words">{msg.body || ""}</p>
        <div className={`flex items-center justify-end gap-1 mt-1 ${isOut ? "text-green-100" : "text-nb-muted"}`}>
          <span className="text-[10px]">{formatTime(msg.created_at)}</span>
          {isOut && (
            <span className="text-[10px]">
              {msg.status === "read" ? "✓✓" : msg.status === "delivered" ? "✓✓" : "✓"}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyPanel() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-8">
      <div className="w-12 h-12 rounded-full bg-nb-elevated border border-nb-border flex items-center justify-center mb-4">
        <svg className="w-6 h-6 text-nb-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
      </div>
      <h2 className="text-sm font-medium text-nb-secondary">Selecione uma conversa</h2>
      <p className="text-xs text-nb-muted mt-1 max-w-xs">
        As mensagens recebidas via WhatsApp aparecem aqui.
      </p>
    </div>
  );
}

// ── No conversations ──────────────────────────────────────────────────────────

function EmptyList() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-6 py-12">
      <div className="w-10 h-10 rounded-full bg-nb-elevated border border-nb-border flex items-center justify-center mb-3">
        <svg className="w-5 h-5 text-nb-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
      </div>
      <p className="text-xs text-nb-muted">Nenhuma conversa ainda.</p>
      <p className="text-xs text-nb-muted mt-1">Envie uma mensagem para o número oficial para iniciar.</p>
    </div>
  );
}

// ── Thread panel ──────────────────────────────────────────────────────────────

function ThreadPanel({
  conv,
  onMessageSent,
}: {
  conv: MetaReviewConversation;
  onMessageSent: () => void;
}) {
  const [messages, setMessages] = useState<MetaReviewMessage[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [templates, setTemplates] = useState<MetaReviewTemplate[]>([]);
  const [showTemplates, setShowTemplates] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadMessages = useCallback(async () => {
    try {
      const msgs = await api.metaReview.getConversationMessages(conv.id);
      setMessages(msgs);
    } catch {}
  }, [conv.id]);

  async function loadTemplates() {
    try {
      const tpls = await api.metaReview.listTemplates();
      setTemplates(tpls);
    } catch {}
  }

  useEffect(() => {
    loadMessages();
    pollRef.current = setInterval(loadMessages, 4000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [loadMessages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    const msg = text.trim();
    if (!msg || sending) return;
    setSending(true);
    setText("");
    try {
      await api.metaReview.sendToConversation(conv.id, msg);
      await loadMessages();
      onMessageSent();
    } catch {
      setText(msg);
    } finally {
      setSending(false);
    }
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-nb-border bg-nb-bg flex-shrink-0">
        <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
          <span className="text-green-700 text-sm font-semibold">
            {contactName(conv).charAt(0).toUpperCase()}
          </span>
        </div>
        <div>
          <p className="text-sm font-medium text-nb-primary">{contactName(conv)}</p>
          <p className="text-xs text-nb-muted">{conv.contact?.phone_e164 ?? ""}</p>
        </div>
        <div className="ml-auto">
          <span className="inline-flex items-center gap-1 text-xs text-green-600 bg-green-50 border border-green-200 rounded-full px-2 py-0.5">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
            WhatsApp Oficial
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-0.5">
        {messages.length === 0 ? (
          <p className="text-center text-xs text-nb-muted mt-8">Nenhuma mensagem ainda.</p>
        ) : (
          messages.map((m) => <Bubble key={m.id} msg={m} />)
        )}
        <div ref={bottomRef} />
      </div>

      {/* Composer */}
      <div className="border-t border-nb-border bg-nb-bg px-4 py-3 flex-shrink-0 relative">
        {/* Template picker popover */}
        {showTemplates && (
          <div className="absolute bottom-full left-4 right-4 mb-2 bg-nb-bg border border-nb-border rounded-xl shadow-lg overflow-hidden max-h-64 overflow-y-auto z-10">
            <div className="flex items-center justify-between px-3 py-2 border-b border-nb-border">
              <span className="text-xs font-medium text-nb-secondary">Templates de mensagem</span>
              <button onClick={() => setShowTemplates(false)} className="text-nb-muted hover:text-nb-primary">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            {templates.length === 0 ? (
              <p className="text-xs text-nb-muted px-3 py-4 text-center">Nenhum template encontrado.</p>
            ) : (
              templates.map((tpl) => (
                <button
                  key={tpl.id}
                  onClick={() => { setText(tpl.body); setShowTemplates(false); }}
                  className="w-full text-left px-3 py-2.5 hover:bg-nb-elevated border-b border-nb-border last:border-0 group"
                >
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-xs font-medium text-nb-primary">{tpl.name}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                      tpl.status === "APPROVED" ? "bg-green-50 text-green-700 border border-green-200" :
                      tpl.status === "REJECTED" ? "bg-red-50 text-red-600 border border-red-200" :
                      "bg-yellow-50 text-yellow-700 border border-yellow-200"
                    }`}>{tpl.status}</span>
                  </div>
                  <p className="text-xs text-nb-muted line-clamp-2">{tpl.body}</p>
                </button>
              ))
            )}
          </div>
        )}
        <div className="flex items-end gap-2">
          <button
            onClick={() => { loadTemplates(); setShowTemplates((v) => !v); }}
            title="Usar template"
            className="w-9 h-9 rounded-full border border-nb-border bg-nb-elevated hover:bg-nb-surface flex items-center justify-center flex-shrink-0 transition-colors"
          >
            <svg className="w-4 h-4 text-nb-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          </button>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Digite uma mensagem…"
            rows={1}
            className="flex-1 resize-none rounded-xl border border-nb-border bg-nb-elevated px-3 py-2 text-sm text-nb-primary placeholder:text-nb-muted focus:outline-none focus:ring-1 focus:ring-nb-accent max-h-32 overflow-y-auto"
            style={{ minHeight: "38px" }}
          />
          <button
            onClick={handleSend}
            disabled={!text.trim() || sending}
            className="w-9 h-9 rounded-full bg-green-500 hover:bg-green-600 disabled:opacity-40 flex items-center justify-center transition-colors flex-shrink-0"
          >
            <svg className="w-4 h-4 text-white rotate-45" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Create Template Modal ─────────────────────────────────────────────────────

function CreateTemplateModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("confirmacao_atendimento");
  const [language, setLanguage] = useState("pt_BR");
  const [category, setCategory] = useState("UTILITY");
  const [body, setBody] = useState("Olá, seu atendimento foi iniciado pelo Wenzap. Em breve nossa equipe continuará a conversa por aqui.");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    try {
      const res = await api.metaReview.createTemplate({ name, language, category, body });
      if (res.success) {
        onClose();
      } else {
        setResult({ success: false, message: `Erro [${res.error?.code}]: ${res.error?.message}` });
        setLoading(false);
      }
    } catch {
      setResult({ success: false, message: "Erro inesperado." });
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="bg-nb-bg border border-nb-border rounded-2xl w-full max-w-md shadow-xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-nb-border">
          <h2 className="text-sm font-semibold text-nb-primary">Criar template de mensagem</h2>
          <button onClick={onClose} className="text-nb-muted hover:text-nb-primary">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="text-xs font-medium text-nb-secondary block mb-1">Nome (snake_case)</label>
            <input value={name} onChange={e => setName(e.target.value)} required
              className="w-full rounded-lg border border-nb-border bg-nb-elevated px-3 py-2 text-sm text-nb-primary focus:outline-none focus:ring-1 focus:ring-nb-accent" />
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-xs font-medium text-nb-secondary block mb-1">Idioma</label>
              <input value={language} onChange={e => setLanguage(e.target.value)} required
                className="w-full rounded-lg border border-nb-border bg-nb-elevated px-3 py-2 text-sm text-nb-primary focus:outline-none focus:ring-1 focus:ring-nb-accent" />
            </div>
            <div className="flex-1">
              <label className="text-xs font-medium text-nb-secondary block mb-1">Categoria</label>
              <select value={category} onChange={e => setCategory(e.target.value)}
                className="w-full rounded-lg border border-nb-border bg-nb-elevated px-3 py-2 text-sm text-nb-primary focus:outline-none focus:ring-1 focus:ring-nb-accent">
                <option value="UTILITY">UTILITY</option>
                <option value="MARKETING">MARKETING</option>
                <option value="AUTHENTICATION">AUTHENTICATION</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-nb-secondary block mb-1">Corpo</label>
            <textarea value={body} onChange={e => setBody(e.target.value)} required rows={3}
              className="w-full rounded-lg border border-nb-border bg-nb-elevated px-3 py-2 text-sm text-nb-primary focus:outline-none focus:ring-1 focus:ring-nb-accent resize-none" />
          </div>
          {result && (
            <p className={`text-xs rounded-lg px-3 py-2 ${result.success ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-600 border border-red-200"}`}>
              {result.message}
            </p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-nb-secondary hover:text-nb-primary">Cancelar</button>
            <button type="submit" disabled={loading}
              className="px-4 py-2 text-sm font-medium bg-nb-accent text-white rounded-lg hover:opacity-90 disabled:opacity-50">
              {loading ? "Criando…" : "Criar template"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function MetaReviewPage() {
  const [conversations, setConversations] = useState<MetaReviewConversation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showTemplateModal, setShowTemplateModal] = useState(false);

  const loadConversations = useCallback(async () => {
    try {
      const convs = await api.metaReview.listConversations();
      setConversations(convs);
      setError(null);
    } catch (e: unknown) {
      if (e instanceof Error) setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConversations();
    const interval = setInterval(loadConversations, 8000);
    return () => clearInterval(interval);
  }, [loadConversations]);

  const selected = conversations.find((c) => c.id === selectedId) ?? null;

  if (error) {
    return (
      <div className="-m-6 flex items-center justify-center" style={{ height: "calc(100vh - 3.5rem)" }}>
        <div className="text-center px-6">
          <p className="text-sm text-red-500 font-medium">Acesso negado</p>
          <p className="text-xs text-nb-muted mt-1">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="-m-6 flex overflow-hidden" style={{ height: "calc(100vh - 3.5rem)" }}>
      {/* Left panel — conversation list */}
      <aside className="w-72 flex-shrink-0 bg-nb-bg border-r border-nb-border flex flex-col overflow-hidden">
        <div className="px-4 py-3 border-b border-nb-border flex-shrink-0">
          <div className="flex items-center justify-between">
            <h1 className="text-sm font-semibold text-nb-primary">Inbox WhatsApp</h1>
            <button
              onClick={() => setShowTemplateModal(true)}
              title="Criar template"
              className="flex items-center gap-1 text-xs text-nb-accent hover:opacity-80 transition-opacity"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Template
            </button>
          </div>
          <p className="text-xs text-nb-muted mt-0.5">Canal oficial · App Review</p>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-4 h-4 border-2 border-nb-accent border-t-transparent rounded-full animate-spin" />
            </div>
          ) : conversations.length === 0 ? (
            <EmptyList />
          ) : (
            conversations.map((conv) => (
              <ConversationItem
                key={conv.id}
                conv={conv}
                selected={conv.id === selectedId}
                onClick={() => setSelectedId(conv.id)}
              />
            ))
          )}
        </div>
      </aside>

      {/* Right panel — thread */}
      <main className="flex-1 bg-nb-bg min-w-0 overflow-hidden">
        {selected ? (
          <ThreadPanel conv={selected} onMessageSent={loadConversations} />
        ) : (
          <EmptyPanel />
        )}
      </main>

      {showTemplateModal && <CreateTemplateModal onClose={() => setShowTemplateModal(false)} />}
    </div>
  );
}
