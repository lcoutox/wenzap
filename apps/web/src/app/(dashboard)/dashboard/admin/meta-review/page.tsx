"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type {
  MetaReviewLog,
  MetaReviewMessage,
  MetaReviewStatus,
  MetaReviewTemplate,
} from "@/lib/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${ok ? "bg-green-500" : "bg-red-500"}`}
    />
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-nb-panel border border-nb-border rounded-2xl p-5 space-y-4">
      <h2 className="text-sm font-semibold text-nb-secondary">{title}</h2>
      {children}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-nb-muted">{label}</span>
      <span className="font-mono text-nb-secondary">{value}</span>
    </div>
  );
}

function Badge({ ok }: { ok: boolean }) {
  return (
    <span
      className={`text-xs font-medium px-2 py-0.5 rounded-md ${
        ok ? "bg-green-500/10 text-green-600" : "bg-red-500/10 text-red-600"
      }`}
    >
      {ok ? "OK" : "Ausente"}
    </span>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function MetaReviewPage() {
  const [envStatus, setEnvStatus] = useState<MetaReviewStatus | null>(null);
  const [accessError, setAccessError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Send test
  const [sendTo, setSendTo] = useState("");
  const [sendMessage, setSendMessage] = useState(
    "Olá! Esta é uma mensagem de teste enviada pelo Wenzap via API oficial do WhatsApp."
  );
  const [sendResult, setSendResult] = useState<string | null>(null);
  const [sendLoading, setSendLoading] = useState(false);

  // Template
  const [tmplName, setTmplName] = useState("confirmacao_atendimento");
  const [tmplLanguage, setTmplLanguage] = useState("pt_BR");
  const [tmplCategory, setTmplCategory] = useState("UTILITY");
  const [tmplBody, setTmplBody] = useState(
    "Olá, seu atendimento foi iniciado pelo Wenzap. Em breve nossa equipe continuará a conversa por aqui."
  );
  const [tmplResult, setTmplResult] = useState<string | null>(null);
  const [tmplLoading, setTmplLoading] = useState(false);

  // Lists
  const [templates, setTemplates] = useState<MetaReviewTemplate[]>([]);
  const [messages, setMessages] = useState<MetaReviewMessage[]>([]);
  const [logs, setLogs] = useState<MetaReviewLog[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const [status, tmpl, msgs, lg] = await Promise.all([
          api.metaReview.status(),
          api.metaReview.listTemplates(),
          api.metaReview.listMessages(),
          api.metaReview.listLogs(),
        ]);
        setEnvStatus(status);
        setTemplates(tmpl);
        setMessages(msgs);
        setLogs(lg);
      } catch (e) {
        if (e instanceof ApiError && (e.status === 403 || e.status === 401)) {
          setAccessError("Acesso negado. Verifique se seu e-mail está em META_REVIEW_ADMIN_EMAILS e se você é owner do workspace.");
        } else {
          setAccessError(e instanceof Error ? e.message : "Erro ao carregar.");
        }
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function refreshLists() {
    try {
      const [tmpl, msgs, lg] = await Promise.all([
        api.metaReview.listTemplates(),
        api.metaReview.listMessages(),
        api.metaReview.listLogs(),
      ]);
      setTemplates(tmpl);
      setMessages(msgs);
      setLogs(lg);
    } catch {}
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    setSendLoading(true);
    setSendResult(null);
    try {
      const res = await api.metaReview.sendTest(sendTo, sendMessage);
      if (res.success) {
        setSendResult(`✓ Enviado! Message ID: ${res.message_id}`);
      } else {
        setSendResult(`✗ Erro [${res.error?.code}]: ${res.error?.message}`);
      }
      await refreshLists();
    } catch (e) {
      setSendResult(`✗ ${e instanceof Error ? e.message : "Erro desconhecido"}`);
    } finally {
      setSendLoading(false);
    }
  }

  async function handleCreateTemplate(e: React.FormEvent) {
    e.preventDefault();
    setTmplLoading(true);
    setTmplResult(null);
    try {
      const res = await api.metaReview.createTemplate({
        name: tmplName,
        language: tmplLanguage,
        category: tmplCategory,
        body: tmplBody,
      });
      if (res.success) {
        setTmplResult(`✓ Template criado! Meta ID: ${res.meta_template_id} · Status: ${res.status}`);
      } else {
        setTmplResult(`✗ Erro [${res.error?.code}]: ${res.error?.message}`);
      }
      await refreshLists();
    } catch (e) {
      setTmplResult(`✗ ${e instanceof Error ? e.message : "Erro desconhecido"}`);
    } finally {
      setTmplLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse max-w-3xl">
        <div className="h-8 w-80 bg-nb-panel rounded-xl" />
        <div className="h-40 bg-nb-panel rounded-2xl border border-nb-border" />
        <div className="h-60 bg-nb-panel rounded-2xl border border-nb-border" />
      </div>
    );
  }

  if (accessError) {
    return (
      <div className="max-w-xl p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-600">
        {accessError}
      </div>
    );
  }

  const webhookUrl = `${typeof window !== "undefined" ? window.location.origin.replace("3000", "8000") : ""}/webhooks/meta/whatsapp`;

  return (
    <div className="max-w-3xl space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-nb-primary-text">
          WhatsApp Oficial — Revisão Meta
        </h1>
        <p className="text-xs text-nb-muted mt-0.5">
          Tela interna para gravação dos vídeos de App Review da Meta. Não é visível para clientes.
        </p>
      </div>

      {/* Seção 1 — Status ENV */}
      {envStatus && (
        <Section title="Configuração detectada">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-nb-muted">Access Token</span>
              <Badge ok={envStatus.has_access_token} />
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-nb-muted">WABA ID</span>
              <div className="flex items-center gap-2">
                <span className="font-mono text-nb-secondary text-xs">{envStatus.waba_id_masked}</span>
                <Badge ok={envStatus.has_waba_id} />
              </div>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-nb-muted">Phone Number ID</span>
              <div className="flex items-center gap-2">
                <span className="font-mono text-nb-secondary text-xs">{envStatus.phone_number_id_masked}</span>
                <Badge ok={envStatus.has_phone_number_id} />
              </div>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-nb-muted">Webhook Verify Token</span>
              <Badge ok={envStatus.has_webhook_verify_token} />
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-nb-muted">Validação de assinatura</span>
              <Badge ok={envStatus.webhook_signature_required} />
            </div>
            <div className="flex items-center justify-between text-sm pt-1 border-t border-nb-border">
              <span className="text-nb-muted">Webhook URL</span>
              <span className="font-mono text-nb-secondary text-xs">{webhookUrl}</span>
            </div>
          </div>

          <div className="mt-3 p-3 bg-amber-500/5 border border-amber-500/20 rounded-xl text-xs text-amber-700 space-y-1">
            <p className="font-medium">⚠ Janela de atendimento</p>
            <p>
              Antes de enviar uma mensagem livre, envie uma mensagem do WhatsApp destinatário para o número oficial da
              Nexalt. Isso abre a janela de 24h da Meta. Sem ela, mensagens livres são bloqueadas.
            </p>
            <p className="mt-1 font-medium">⚠ Pagamento na Meta</p>
            <p>
              Se a Meta exibir "Adicione informações de pagamento para enviar mensagens iniciadas pela empresa",
              você precisa configurar pagamento no Meta Business antes de enviar templates ou mensagens outbound.
            </p>
          </div>
        </Section>
      )}

      {/* Seção 2 — Enviar mensagem de teste */}
      <Section title="Enviar mensagem de teste">
        <form onSubmit={handleSend} className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-nb-muted mb-1">
              Destinatário (com código do país, ex: 5537999999999)
            </label>
            <input
              type="text"
              value={sendTo}
              onChange={(e) => setSendTo(e.target.value)}
              placeholder="5537999999999"
              required
              className="w-full bg-nb-bg border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-secondary focus:outline-none focus:border-nb-primary"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-nb-muted mb-1">Mensagem</label>
            <textarea
              value={sendMessage}
              onChange={(e) => setSendMessage(e.target.value)}
              rows={3}
              required
              className="w-full bg-nb-bg border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-secondary focus:outline-none focus:border-nb-primary resize-none"
            />
          </div>
          <button
            type="submit"
            disabled={sendLoading}
            className="px-4 py-2 bg-nb-primary text-white text-sm font-medium rounded-xl hover:bg-nb-primary/90 disabled:opacity-50"
          >
            {sendLoading ? "Enviando..." : "Enviar mensagem de teste"}
          </button>
          {sendResult && (
            <p className={`text-xs font-mono mt-2 ${sendResult.startsWith("✓") ? "text-green-600" : "text-red-600"}`}>
              {sendResult}
            </p>
          )}
        </form>
      </Section>

      {/* Seção 3 — Criar template */}
      <Section title="Criar modelo de mensagem (whatsapp_business_management)">
        <form onSubmit={handleCreateTemplate} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-nb-muted mb-1">Nome (snake_case)</label>
              <input
                type="text"
                value={tmplName}
                onChange={(e) => setTmplName(e.target.value)}
                required
                className="w-full bg-nb-bg border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-secondary focus:outline-none focus:border-nb-primary"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-nb-muted mb-1">Idioma</label>
              <input
                type="text"
                value={tmplLanguage}
                onChange={(e) => setTmplLanguage(e.target.value)}
                required
                className="w-full bg-nb-bg border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-secondary focus:outline-none focus:border-nb-primary"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-nb-muted mb-1">Categoria</label>
            <select
              value={tmplCategory}
              onChange={(e) => setTmplCategory(e.target.value)}
              className="w-full bg-nb-bg border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-secondary focus:outline-none focus:border-nb-primary"
            >
              <option value="UTILITY">UTILITY</option>
              <option value="MARKETING">MARKETING</option>
              <option value="AUTHENTICATION">AUTHENTICATION</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-nb-muted mb-1">
              Corpo (sem {"{{variáveis}}"} para evitar rejeição)
            </label>
            <textarea
              value={tmplBody}
              onChange={(e) => setTmplBody(e.target.value)}
              rows={3}
              required
              className="w-full bg-nb-bg border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-secondary focus:outline-none focus:border-nb-primary resize-none"
            />
          </div>
          <button
            type="submit"
            disabled={tmplLoading}
            className="px-4 py-2 bg-nb-primary text-white text-sm font-medium rounded-xl hover:bg-nb-primary/90 disabled:opacity-50"
          >
            {tmplLoading ? "Criando..." : "Criar modelo na Meta"}
          </button>
          {tmplResult && (
            <p className={`text-xs font-mono mt-2 ${tmplResult.startsWith("✓") ? "text-green-600" : "text-red-600"}`}>
              {tmplResult}
            </p>
          )}
        </form>
      </Section>

      {/* Seção 4 — Templates */}
      {templates.length > 0 && (
        <Section title="Templates criados">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-nb-muted border-b border-nb-border">
                  <th className="pb-2 font-medium">Nome</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium">Meta ID</th>
                  <th className="pb-2 font-medium">Criado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-nb-border">
                {templates.map((t) => (
                  <tr key={t.id}>
                    <td className="py-2 font-mono text-nb-secondary">{t.name}</td>
                    <td className="py-2 text-nb-muted">{t.status}</td>
                    <td className="py-2 font-mono text-nb-muted">{t.meta_template_id ?? "—"}</td>
                    <td className="py-2 text-nb-muted">{new Date(t.created_at).toLocaleString("pt-BR")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {/* Seção 5 — Mensagens */}
      {messages.length > 0 && (
        <Section title="Mensagens">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-nb-muted border-b border-nb-border">
                  <th className="pb-2 font-medium">Data</th>
                  <th className="pb-2 font-medium">Dir</th>
                  <th className="pb-2 font-medium">Mensagem</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium">Message ID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-nb-border">
                {messages.map((m) => (
                  <tr key={m.id}>
                    <td className="py-2 text-nb-muted whitespace-nowrap">{new Date(m.created_at).toLocaleString("pt-BR")}</td>
                    <td className="py-2">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${m.direction === "outbound" ? "bg-blue-500/10 text-blue-600" : "bg-green-500/10 text-green-600"}`}>
                        {m.direction}
                      </span>
                    </td>
                    <td className="py-2 text-nb-secondary max-w-xs truncate">{m.body ?? "—"}</td>
                    <td className="py-2 text-nb-muted">{m.status ?? "—"}</td>
                    <td className="py-2 font-mono text-nb-muted text-[10px]">{m.meta_message_id ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {/* Seção 6 — Logs */}
      <Section title="Logs">
        <div className="flex justify-end mb-1">
          <button
            type="button"
            onClick={refreshLists}
            className="text-xs text-nb-primary underline hover:no-underline"
          >
            Atualizar
          </button>
        </div>
        {logs.length === 0 ? (
          <p className="text-xs text-nb-muted">Nenhum log ainda.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-nb-muted border-b border-nb-border">
                  <th className="pb-2 font-medium">Data</th>
                  <th className="pb-2 font-medium">Tipo</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium">Resumo</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-nb-border">
                {logs.map((l) => (
                  <tr key={l.id}>
                    <td className="py-2 text-nb-muted whitespace-nowrap">{new Date(l.created_at).toLocaleString("pt-BR")}</td>
                    <td className="py-2 font-mono text-nb-secondary">{l.event_type}</td>
                    <td className="py-2">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${l.status === "success" || l.status === "received" ? "bg-green-500/10 text-green-600" : "bg-red-500/10 text-red-600"}`}>
                        {l.status}
                      </span>
                    </td>
                    <td className="py-2 text-nb-muted max-w-sm truncate">{l.summary ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  );
}
