import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Política de Privacidade — Wenzap",
  description: "Saiba como o Wenzap coleta, usa e protege seus dados pessoais.",
  robots: { index: true, follow: true },
};

export default function PrivacidadePage() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-16">
      <h1 className="text-3xl font-bold text-nb-primary mb-2">Política de Privacidade</h1>
      <p className="text-sm text-nb-muted mb-10">Última atualização: julho de 2026</p>

      <div className="prose prose-sm max-w-none text-nb-secondary space-y-8">

        <section>
          <h2 className="text-lg font-semibold text-nb-primary mb-2">1. Quem somos</h2>
          <p>
            O Wenzap é uma plataforma de agentes de IA para atendimento e operações empresariais,
            desenvolvida e operada pela <strong>ORBIT HUB SOFTWARE LTDA</strong>, inscrita no CNPJ
            54.414.617/0001-82, com sede no Brasil.
          </p>
          <p className="mt-2">
            Para dúvidas sobre esta política ou sobre seus dados, entre em contato:
            <br />
            <a href="mailto:privacidade@wenzap.com.br" className="text-nb-accent underline">
              privacidade@wenzap.com.br
            </a>
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-nb-primary mb-2">2. Dados que coletamos</h2>
          <p>Coletamos os seguintes tipos de dados:</p>
          <ul className="list-disc pl-5 mt-2 space-y-1">
            <li><strong>Dados de cadastro:</strong> nome, e-mail, empresa e telefone fornecidos ao criar uma conta.</li>
            <li><strong>Dados de uso:</strong> interações com a plataforma, logs de acesso, preferências e configurações.</li>
            <li><strong>Dados de conversas:</strong> mensagens trocadas entre empresas e seus clientes finais via canais conectados (WhatsApp, widget, etc.).</li>
            <li><strong>Dados de contatos:</strong> informações de contatos cadastrados pelas empresas clientes (nome, telefone, e-mail).</li>
            <li><strong>Dados técnicos:</strong> endereço IP, tipo de navegador, sistema operacional e identificadores de dispositivo.</li>
            <li><strong>Cookies e rastreadores:</strong> utilizados para manter sessões autenticadas e medir uso do produto.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-nb-primary mb-2">3. Como usamos seus dados</h2>
          <ul className="list-disc pl-5 space-y-1">
            <li>Prestar e melhorar os serviços do Wenzap.</li>
            <li>Processar e entregar mensagens via WhatsApp Cloud API e outros canais.</li>
            <li>Enviar notificações sobre o serviço, atualizações e comunicados importantes.</li>
            <li>Cumprir obrigações legais e regulatórias.</li>
            <li>Prevenir fraudes e garantir a segurança da plataforma.</li>
            <li>Gerar métricas agregadas e anônimas para análise de produto.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-nb-primary mb-2">4. WhatsApp Cloud API</h2>
          <p>
            O Wenzap utiliza a <strong>WhatsApp Cloud API</strong> (Meta Platforms, Inc.) para
            envio e recebimento de mensagens. Ao usar canais WhatsApp na plataforma, você concorda
            que mensagens são transmitidas via infraestrutura da Meta, sujeitas às políticas de
            uso da Meta Business Platform.
          </p>
          <p className="mt-2">
            Não armazenamos o conteúdo de mensagens além do necessário para exibição no Inbox e
            auditoria operacional. Chaves de acesso à API da Meta são armazenadas com criptografia
            e nunca são expostas no frontend.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-nb-primary mb-2">5. Compartilhamento de dados</h2>
          <p>Não vendemos seus dados. Podemos compartilhá-los apenas com:</p>
          <ul className="list-disc pl-5 mt-2 space-y-1">
            <li><strong>Provedores de infraestrutura:</strong> servidores em nuvem (Railway, Cloudflare) necessários para operar o serviço.</li>
            <li><strong>Provedores de IA:</strong> Anthropic e OpenAI, para processar mensagens com modelos de linguagem. Apenas o conteúdo necessário é enviado.</li>
            <li><strong>Meta Platforms:</strong> para entrega de mensagens via WhatsApp Cloud API.</li>
            <li><strong>Autoridades:</strong> quando exigido por lei ou ordem judicial.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-nb-primary mb-2">6. Retenção de dados</h2>
          <p>
            Mantemos seus dados enquanto sua conta estiver ativa. Após o encerramento, os dados
            são excluídos ou anonimizados em até 90 dias, salvo obrigação legal de retenção maior.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-nb-primary mb-2">7. Seus direitos (LGPD)</h2>
          <p>Nos termos da Lei Geral de Proteção de Dados (Lei 13.709/2018), você tem direito a:</p>
          <ul className="list-disc pl-5 mt-2 space-y-1">
            <li>Confirmar a existência de tratamento de dados.</li>
            <li>Acessar seus dados pessoais.</li>
            <li>Corrigir dados incompletos, inexatos ou desatualizados.</li>
            <li>Solicitar anonimização, bloqueio ou eliminação de dados.</li>
            <li>Portabilidade dos dados a outro fornecedor de serviço.</li>
            <li>Revogar consentimento a qualquer momento.</li>
          </ul>
          <p className="mt-2">
            Para exercer esses direitos, envie e-mail para{" "}
            <a href="mailto:privacidade@wenzap.com.br" className="text-nb-accent underline">
              privacidade@wenzap.com.br
            </a>
            .
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-nb-primary mb-2">8. Segurança</h2>
          <p>
            Adotamos medidas técnicas e organizacionais para proteger seus dados, incluindo
            criptografia em trânsito (TLS), criptografia de credenciais em repouso, controle de
            acesso por função e logs de auditoria. Nenhum sistema é 100% seguro — em caso de
            incidente, notificaremos os titulares afetados conforme a LGPD.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-nb-primary mb-2">9. Cookies</h2>
          <p>
            Utilizamos cookies essenciais para manter sessões autenticadas e cookies de análise
            para entender como o produto é usado (dados agregados e anônimos). Não utilizamos
            cookies de publicidade comportamental de terceiros.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-nb-primary mb-2">10. Alterações nesta política</h2>
          <p>
            Podemos atualizar esta política periodicamente. Alterações relevantes serão comunicadas
            por e-mail ou aviso na plataforma. O uso continuado após a notificação implica
            aceitação das mudanças.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-nb-primary mb-2">11. Contato</h2>
          <p>
            ORBIT HUB SOFTWARE LTDA<br />
            CNPJ: 54.414.617/0001-82<br />
            E-mail:{" "}
            <a href="mailto:privacidade@wenzap.com.br" className="text-nb-accent underline">
              privacidade@wenzap.com.br
            </a>
          </p>
        </section>

      </div>
    </main>
  );
}
