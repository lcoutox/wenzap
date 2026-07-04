"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MessageCircle, Send, X, AlertTriangle } from "lucide-react";
import { publicWidgetApi } from "@/lib/publicWidgetApi";
import type { ContactCaptureData, PublicWidgetConfig, WidgetMessage, WidgetPageContext } from "@/lib/publicWidgetApi";

// ── Markdown renderer (no external deps) ─────────────────────────────────────
// Supports: **bold**, *italic*, \n line breaks. Safe — no dangerouslySetInnerHTML.

function renderMarkdown(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  // Split on newlines first, then parse inline tokens per line.
  const lines = text.split("\n");
  lines.forEach((line, li) => {
    if (li > 0) nodes.push(<br key={`br-${li}`} />);
    // Tokenize inline: **bold** | *italic* | plain text
    const parts = line.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
    parts.forEach((part, pi) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        nodes.push(<strong key={`${li}-${pi}`}>{part.slice(2, -2)}</strong>);
      } else if (part.startsWith("*") && part.endsWith("*")) {
        nodes.push(<em key={`${li}-${pi}`}>{part.slice(1, -1)}</em>);
      } else {
        nodes.push(part);
      }
    });
  });
  return nodes;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const POLL_INTERVAL_MS = 2000;
const POLL_MAX_ATTEMPTS = 3;
const PASSIVE_POLL_INTERVAL_MS = 5000;

// ── localStorage helpers ──────────────────────────────────────────────────────

function storageKey(publicKey: string) {
  return `nb_widget_session_${publicKey}`;
}

function readStoredToken(publicKey: string): string | undefined {
  try {
    return localStorage.getItem(storageKey(publicKey)) ?? undefined;
  } catch {
    return undefined;
  }
}

function saveToken(publicKey: string, token: string) {
  try {
    localStorage.setItem(storageKey(publicKey), token);
  } catch {
    // Ignore — private browsing may block storage.
  }
}

// ── Theme helpers ─────────────────────────────────────────────────────────────

type Theme = "dark" | "light" | "auto";

function resolveTheme(theme: Theme): "dark" | "light" {
  if (theme === "auto") {
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }
  return theme;
}

// ── Theming token maps ────────────────────────────────────────────────────────

const DARK = {
  bg: "#0C1220",
  surface: "#111827",
  elevated: "#172033",
  border: "#253044",
  text: "#F4F7FB",
  secondary: "#A8B3C7",
  muted: "#6F7B90",
  inputBg: "#172033",
  customerBg: "var(--widget-primary)",
  customerText: "#ffffff",
  agentBg: "#172033",
  agentText: "#F4F7FB",
  loadingText: "#6F7B90",
  errorBg: "rgba(251,113,133,0.10)",
  errorBorder: "rgba(251,113,133,0.30)",
  errorText: "#FB7185",
};

const LIGHT = {
  bg: "#ffffff",
  surface: "#f8fafc",
  elevated: "#f1f5f9",
  border: "#e2e8f0",
  text: "#111827",
  secondary: "#374151",
  muted: "#6b7280",
  inputBg: "#f8fafc",
  customerBg: "var(--widget-primary)",
  customerText: "#ffffff",
  agentBg: "#f1f5f9",
  agentText: "#111827",
  loadingText: "#9ca3af",
  errorBg: "#fff1f2",
  errorBorder: "#fca5a5",
  errorText: "#dc2626",
};

// ── Scroll helper ─────────────────────────────────────────────────────────────

function scrollToBottom(el: HTMLDivElement | null) {
  if (el) el.scrollTop = el.scrollHeight;
}

// ── Optimistic message ────────────────────────────────────────────────────────

function makeOptimistic(content: string): WidgetMessage {
  return {
    id: `opt_${Date.now()}`,
    direction: "inbound",
    sender_type: "customer",
    content,
    created_at: new Date().toISOString(),
  };
}

// ── WidgetEmbed ───────────────────────────────────────────────────────────────

export function WidgetEmbed({ publicKey }: { publicKey: string }) {
  const [configStatus, setConfigStatus] = useState<"loading" | "ready" | "error">("loading");
  const [config, setConfig] = useState<PublicWidgetConfig | null>(null);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [messages, setMessages] = useState<WidgetMessage[]>([]);
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [polling, setPolling] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [initDone, setInitDone] = useState(false);
  // If wenzap:open arrives before config is ready, honour it once ready.
  const pendingOpenRef = useRef(false);
  // Contact capture state
  const [contactCaptured, setContactCaptured] = useState(true); // true = no form needed
  const [captureForm, setCaptureForm] = useState<ContactCaptureData>({});
  const [captureError, setCaptureError] = useState<string | null>(null);
  const [captureSubmitting, setCaptureSubmitting] = useState(false);

  const messagesRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const pageContextRef = useRef<WidgetPageContext | null>(null);
  // Resolver called by the message listener to unblock init early.
  const pageContextResolverRef = useRef<(() => void) | null>(null);

  // ── Initialization ──────────────────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false;

    // Register page-context listener immediately so it can fire before or during init.
    function handleMessage(event: MessageEvent) {
      if (!event.data || event.data.type !== "wenzap:page-context") return;
      const ctx = event.data.pageContext as WidgetPageContext | undefined;
      if (ctx && typeof ctx === "object") {
        pageContextRef.current = ctx;
      }
      // If init is already waiting, unblock it now.
      pageContextResolverRef.current?.();
      pageContextResolverRef.current = null;
    }
    window.addEventListener("message", handleMessage);

    async function init() {
      try {
        // 1. Fetch config — set ready before any session work so the widget
        //    renders with the real colours/avatar and no flash.
        const cfg = await publicWidgetApi.getConfig(publicKey);
        if (cancelled) return;
        setConfig(cfg);
        setConfigStatus("ready");

        // 2. Wait for pageContext from widget.js, or fall back after 600ms.
        //    The Promise resolves early if the listener fires first.
        await new Promise<void>((resolve) => {
          if (pageContextRef.current !== null) {
            resolve();
            return;
          }
          pageContextResolverRef.current = resolve;
          setTimeout(() => {
            pageContextResolverRef.current = null;
            resolve();
          }, 600);
        });
        if (cancelled) return;

        // 3. Create or resume session — page context is now available (or absent).
        const storedToken = readStoredToken(publicKey);
        const { session_token, contact_captured } =
          await publicWidgetApi.createOrResumeSession(
            publicKey,
            storedToken,
            pageContextRef.current ?? undefined,
          );
        if (cancelled) return;
        saveToken(publicKey, session_token);
        setSessionToken(session_token);
        setContactCaptured(contact_captured);

        // 3. Load history
        const history = await publicWidgetApi.listMessages(publicKey, session_token);
        if (cancelled) return;
        setMessages(history);
        setInitDone(true);

        // 4. Notify parent iframe about position so widget.js can reposition.
        try {
          window.parent.postMessage(
            { type: "wenzap:widget-config", position: cfg.position },
            "*",
          );
        } catch {
          // Sandboxed iframe or same-origin — ignore.
        }

        // 5. Auto-open or honour a pending open requested before config was ready.
        if (cfg.auto_open || pendingOpenRef.current) {
          pendingOpenRef.current = false;
          const delay = cfg.auto_open ? (cfg.auto_open_delay_seconds ?? 0) * 1000 : 0;
          setTimeout(() => {
            if (!cancelled) setOpen(true);
          }, delay);
        }
      } catch {
        if (!cancelled) {
          setConfigStatus("error");
          setInitError("Não foi possível carregar o atendimento. Tente recarregar a página.");
        }
      }
    }

    init();
    return () => {
      cancelled = true;
      window.removeEventListener("message", handleMessage);
      // Unblock any pending wait so it doesn't hold a stale resolver.
      pageContextResolverRef.current?.();
      pageContextResolverRef.current = null;
    };
  }, [publicKey]);

  // Passive polling: refresh messages every 5s while chat is open.
  // Silently updates — no error shown on failure. Deduplication is handled
  // by replacing the messages array entirely (server is the source of truth).
  useEffect(() => {
    if (!open || !sessionToken || !initDone) return;

    const id = setInterval(async () => {
      try {
        const updated = await publicWidgetApi.listMessages(publicKey, sessionToken);
        setMessages((prev) => {
          // Only update if something actually changed to avoid unnecessary re-renders.
          if (
            updated.length === prev.length &&
            updated.every((m, i) => m.id === prev[i].id)
          ) {
            return prev;
          }
          return updated;
        });
      } catch {
        // Fail silently — network hiccups shouldn't disrupt the visitor.
      }
    }, PASSIVE_POLL_INTERVAL_MS);

    return () => clearInterval(id);
  }, [open, sessionToken, publicKey, initDone]);

  // Allow parent page to open the widget via postMessage { type: "wenzap:open" }.
  // If config is not ready yet, record the intent and honour it once ready.
  useEffect(() => {
    function handleParentMessage(event: MessageEvent) {
      if (!event.data || event.data.type !== "wenzap:open") return;
      if (configStatus === "ready") {
        setOpen(true);
      } else {
        pendingOpenRef.current = true;
      }
    }
    window.addEventListener("message", handleParentMessage);
    return () => window.removeEventListener("message", handleParentMessage);
  }, [configStatus]);

  // Scroll to bottom whenever messages change or chat opens.
  useEffect(() => {
    scrollToBottom(messagesRef.current);
  }, [messages, open]);

  // Focus input when chat opens.
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 150);
  }, [open]);

  // ── Send message ────────────────────────────────────────────────────────────

  const handleSend = useCallback(async () => {
    if (!sessionToken || !input.trim() || sending) return;
    const content = input.trim();

    setInput("");
    setSendError(null);
    setSending(true);

    // Optimistic update
    const optimistic = makeOptimistic(content);
    setMessages((prev) => [...prev, optimistic]);

    try {
      await publicWidgetApi.sendMessage(publicKey, sessionToken, content);

      // Poll for agent reply
      setPolling(true);
      let found = false;
      for (let attempt = 0; attempt < POLL_MAX_ATTEMPTS; attempt++) {
        if (attempt > 0) {
          await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
        }
        const updated = await publicWidgetApi.listMessages(publicKey, sessionToken);
        // Check if there's an outbound message newer than the optimistic one
        const hasReply = updated.some(
          (m) =>
            m.direction === "outbound" &&
            new Date(m.created_at) >= new Date(optimistic.created_at),
        );
        setMessages(updated);
        if (hasReply) { found = true; break; }
      }
      if (!found) {
        // No reply after max attempts — still show latest messages
        const final = await publicWidgetApi.listMessages(publicKey, sessionToken);
        setMessages(final);
      }
    } catch {
      setSendError("Não foi possível enviar sua mensagem. Tente novamente.");
      // Remove optimistic message on failure
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
    } finally {
      setSending(false);
      setPolling(false);
    }
  }, [publicKey, sessionToken, input, sending]);

  // ── Contact capture submit ───────────────────────────────────────────────────

  const handleCaptureSubmit = useCallback(async () => {
    if (!sessionToken || !config) return;
    setCaptureError(null);
    setCaptureSubmitting(true);
    try {
      await publicWidgetApi.updateContact(publicKey, sessionToken, captureForm);
      setContactCaptured(true);
    } catch (err) {
      setCaptureError(
        err instanceof Error ? err.message : "Não foi possível salvar seus dados."
      );
    } finally {
      setCaptureSubmitting(false);
    }
  }, [publicKey, sessionToken, captureForm, config]);

  // ── Keyboard handler ────────────────────────────────────────────────────────

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  // ── Derived values ──────────────────────────────────────────────────────────

  // ── Early exit — render nothing until config is resolved ───────────────────
  if (configStatus === "loading") return null;
  if (configStatus === "error" || !config) return null;

  // ── Derived values (config is guaranteed non-null below) ────────────────────
  const resolvedTheme = resolveTheme(config.theme);
  const t = resolvedTheme === "dark" ? DARK : LIGHT;
  const primaryColor = config.primary_color;
  const position = config.position;
  const isLeft = position === "bottom-left";

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div
      style={{ "--widget-primary": primaryColor } as React.CSSProperties}
      className="fixed inset-0 pointer-events-none"
    >
      <style>{`
        @keyframes nb-typing-bounce {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
          30% { transform: translateY(-5px); opacity: 1; }
        }
      `}</style>
      {/* ── Chat Window ───────────────────────────────────────────────────── */}
      {open && (
        <div
          style={{
            position: "fixed",
            bottom: "80px",
            [isLeft ? "left" : "right"]: "16px",
            width: "360px",
            height: "520px",
            background: t.bg,
            border: `1px solid ${t.border}`,
            borderRadius: "20px",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            boxShadow: "0 24px 64px rgba(0,0,0,0.40)",
            pointerEvents: "auto",
          }}
        >
          {/* Header */}
          <div
            style={{
              background: t.surface,
              borderBottom: `1px solid ${t.border}`,
              padding: "14px 16px",
              display: "flex",
              alignItems: "center",
              gap: "10px",
              flexShrink: 0,
            }}
          >
            {config?.avatar_url ? (
              <img
                src={config.avatar_url}
                alt=""
                style={{ width: 36, height: 36, borderRadius: "50%", objectFit: "cover" }}
              />
            ) : (
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: "50%",
                  background: `${primaryColor}33`,
                  border: `1px solid ${primaryColor}55`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <MessageCircle
                  style={{ width: 16, height: 16, color: primaryColor }}
                />
              </div>
            )}
            <div style={{ flex: 1, minWidth: 0 }}>
              <p
                style={{
                  margin: 0,
                  fontSize: 14,
                  fontWeight: 600,
                  color: t.text,
                  lineHeight: 1.3,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {config?.header_title ?? "Atendimento"}
              </p>
              <p
                style={{
                  margin: 0,
                  fontSize: 11,
                  color: t.muted,
                  lineHeight: 1.3,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {config?.header_subtitle ?? ""}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: 4,
                borderRadius: 8,
                color: t.muted,
                display: "flex",
                alignItems: "center",
                flexShrink: 0,
              }}
              aria-label="Fechar chat"
            >
              <X style={{ width: 16, height: 16 }} />
            </button>
          </div>

          {/* Contact capture form */}
          {!contactCaptured && config?.contact_capture_enabled && (
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                padding: "20px 16px",
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
            >
              <p style={{ margin: 0, fontSize: 13, color: t.muted, lineHeight: 1.5 }}>
                Antes de continuar, precisamos de algumas informações.
              </p>
              {config.require_name && (
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <label style={{ fontSize: 12, color: t.muted, fontWeight: 500 }}>Nome</label>
                  <input
                    type="text"
                    placeholder="Seu nome"
                    value={captureForm.name ?? ""}
                    onChange={(e) => setCaptureForm((f) => ({ ...f, name: e.target.value }))}
                    style={{
                      background: t.inputBg,
                      border: `1px solid ${t.border}`,
                      borderRadius: 10,
                      padding: "8px 12px",
                      fontSize: 13,
                      color: t.text,
                      outline: "none",
                      fontFamily: "inherit",
                    }}
                  />
                </div>
              )}
              {config.require_email && (
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <label style={{ fontSize: 12, color: t.muted, fontWeight: 500 }}>E-mail</label>
                  <input
                    type="email"
                    placeholder="seu@email.com"
                    value={captureForm.email ?? ""}
                    onChange={(e) => setCaptureForm((f) => ({ ...f, email: e.target.value }))}
                    style={{
                      background: t.inputBg,
                      border: `1px solid ${t.border}`,
                      borderRadius: 10,
                      padding: "8px 12px",
                      fontSize: 13,
                      color: t.text,
                      outline: "none",
                      fontFamily: "inherit",
                    }}
                  />
                </div>
              )}
              {config.require_phone && (
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <label style={{ fontSize: 12, color: t.muted, fontWeight: 500 }}>Telefone</label>
                  <input
                    type="tel"
                    placeholder="+55 (11) 99999-9999"
                    value={captureForm.phone ?? ""}
                    onChange={(e) => setCaptureForm((f) => ({ ...f, phone: e.target.value }))}
                    style={{
                      background: t.inputBg,
                      border: `1px solid ${t.border}`,
                      borderRadius: 10,
                      padding: "8px 12px",
                      fontSize: 13,
                      color: t.text,
                      outline: "none",
                      fontFamily: "inherit",
                    }}
                  />
                </div>
              )}
              {captureError && (
                <p style={{ margin: 0, fontSize: 12, color: t.errorText }}>{captureError}</p>
              )}
              <button
                type="button"
                onClick={handleCaptureSubmit}
                disabled={captureSubmitting}
                style={{
                  background: primaryColor,
                  color: "#fff",
                  border: "none",
                  borderRadius: 10,
                  padding: "10px 0",
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: captureSubmitting ? "not-allowed" : "pointer",
                  opacity: captureSubmitting ? 0.7 : 1,
                  fontFamily: "inherit",
                }}
              >
                {captureSubmitting ? "Enviando..." : "Continuar"}
              </button>
            </div>
          )}

          {/* Messages + input (shown only after contact captured) */}
          {contactCaptured && (<>
          <div
            ref={messagesRef}
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "12px 14px",
              display: "flex",
              flexDirection: "column",
              gap: 8,
              scrollBehavior: "smooth",
            }}
          >
            {/* Init error */}
            {initError && (
              <div
                style={{
                  background: t.errorBg,
                  border: `1px solid ${t.errorBorder}`,
                  borderRadius: 12,
                  padding: "10px 12px",
                  display: "flex",
                  gap: 8,
                  alignItems: "flex-start",
                }}
              >
                <AlertTriangle style={{ width: 14, height: 14, color: t.errorText, flexShrink: 0, marginTop: 1 }} />
                <p style={{ margin: 0, fontSize: 12, color: t.errorText, lineHeight: 1.5 }}>
                  {initError}
                </p>
              </div>
            )}

            {/* Welcome message */}
            {initDone && messages.length === 0 && config?.welcome_message && (
              <div style={{ display: "flex", justifyContent: "flex-start" }}>
                <div
                  style={{
                    background: t.agentBg,
                    color: t.agentText,
                    borderRadius: "16px 16px 16px 4px",
                    padding: "9px 13px",
                    fontSize: 13,
                    maxWidth: "80%",
                    lineHeight: 1.5,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {config.welcome_message}
                </div>
              </div>
            )}

            {/* Conversation messages */}
            {messages.map((msg) => {
              const isCustomer = msg.direction === "inbound";
              return (
                <div
                  key={msg.id}
                  style={{
                    display: "flex",
                    justifyContent: isCustomer ? "flex-end" : "flex-start",
                  }}
                >
                  <div
                    style={{
                      background: isCustomer ? t.customerBg : t.agentBg,
                      color: isCustomer ? t.customerText : t.agentText,
                      borderRadius: isCustomer
                        ? "16px 16px 4px 16px"
                        : "16px 16px 16px 4px",
                      padding: "9px 13px",
                      fontSize: 13,
                      maxWidth: "80%",
                      lineHeight: 1.5,
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                    }}
                  >
                    {isCustomer ? msg.content : renderMarkdown(msg.content)}
                  </div>
                </div>
              );
            })}

            {/* Typing indicator */}
            {(sending || polling) && (
              <div style={{ display: "flex", justifyContent: "flex-start" }}>
                <div
                  style={{
                    background: t.agentBg,
                    borderRadius: "16px 16px 16px 4px",
                    padding: "12px 16px",
                    display: "flex",
                    alignItems: "center",
                    gap: 5,
                  }}
                >
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      style={{
                        display: "block",
                        width: 7,
                        height: 7,
                        borderRadius: "50%",
                        background: t.loadingText,
                        animation: `nb-typing-bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
                      }}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Send error */}
          {sendError && (
            <div
              style={{
                background: t.errorBg,
                borderTop: `1px solid ${t.errorBorder}`,
                padding: "8px 14px",
                display: "flex",
                gap: 6,
                alignItems: "center",
              }}
            >
              <AlertTriangle style={{ width: 13, height: 13, color: t.errorText, flexShrink: 0 }} />
              <p style={{ margin: 0, fontSize: 11, color: t.errorText }}>{sendError}</p>
            </div>
          )}

          {/* Input */}
          <div
            style={{
              borderTop: `1px solid ${t.border}`,
              padding: "10px 12px",
              display: "flex",
              gap: 8,
              alignItems: "flex-end",
              background: t.surface,
              flexShrink: 0,
            }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={sending || !!initError}
              placeholder={config?.placeholder ?? "Digite sua mensagem..."}
              rows={1}
              style={{
                flex: 1,
                background: t.inputBg,
                border: `1px solid ${t.border}`,
                borderRadius: 12,
                padding: "8px 12px",
                fontSize: 13,
                color: t.text,
                resize: "none",
                outline: "none",
                fontFamily: "inherit",
                lineHeight: 1.5,
                maxHeight: 80,
                overflowY: "auto",
              }}
            />
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim() || sending || !!initError}
              style={{
                width: 36,
                height: 36,
                borderRadius: "50%",
                background: !input.trim() || sending ? t.elevated : primaryColor,
                border: "none",
                cursor: !input.trim() || sending ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                transition: "background 0.15s",
              }}
              aria-label="Enviar mensagem"
            >
              <Send
                style={{
                  width: 15,
                  height: 15,
                  color: !input.trim() || sending ? t.muted : "#ffffff",
                }}
              />
            </button>
          </div>
          </>)} {/* end contactCaptured */}

          {/* Powered by Wenzap */}
          <div
            style={{
              borderTop: `1px solid ${t.border}`,
              padding: "5px 0 6px",
              textAlign: "center",
              flexShrink: 0,
            }}
          >
            <span style={{ fontSize: 10, color: t.muted, letterSpacing: "0.01em" }}>
              Powered by{" "}
              <span style={{ fontWeight: 600, color: t.secondary }}>Wenzap</span>
            </span>
          </div>
        </div>
      )}

      {/* ── Launcher Button ────────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Fechar chat" : "Abrir chat"}
        style={{
          position: "fixed",
          bottom: 20,
          [isLeft ? "left" : "right"]: 20,
          width: 52,
          height: 52,
          borderRadius: "50%",
          background: primaryColor,
          border: "none",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: `0 4px 20px ${primaryColor}55`,
          transition: "transform 0.15s, box-shadow 0.15s",
          pointerEvents: "auto",
          zIndex: 10,
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.transform = "scale(1.08)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.transform = "scale(1)";
        }}
      >
        {open ? (
          <X style={{ width: 22, height: 22, color: "#ffffff" }} />
        ) : config?.avatar_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={config.avatar_url}
            alt=""
            style={{ width: 52, height: 52, borderRadius: "50%", objectFit: "cover" }}
          />
        ) : (
          <MessageCircle style={{ width: 22, height: 22, color: "#ffffff" }} />
        )}
      </button>

      {/* Keyframe animation for spinner — injected once */}
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
