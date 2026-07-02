"""
HTML and plain-text email templates for Wenzap transactional emails.

Design direction:
- Dark premium background (#070A12)
- White card, max 600px
- Wenzap brand color (#7C3AED purple)
- Rounded corners, generous spacing
- Mobile-first
- CSS inline (no external fonts, no images required)
- Degrades gracefully when images are blocked
"""


def verification_email_html(verification_url: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Confirme seu e-mail no Wenzap</title>
</head>
<body style="margin:0;padding:0;background-color:#070A12;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">  <!-- noqa: E501 -->

  <!-- Preheader (hidden) -->
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">
    Finalize seu cadastro e libere o acesso ao seu workspace.
    &nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;
  </div>

  <!-- Outer wrapper -->
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
         style="background-color:#070A12;padding:40px 16px;">
    <tr>
      <td align="center">

        <!-- Card -->
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
               style="max-width:580px;background-color:#ffffff;border-radius:20px;overflow:hidden;
                      box-shadow:0 8px 40px rgba(0,0,0,0.5);">

          <!-- Top accent bar -->
          <tr>
            <td style="background:linear-gradient(135deg,#7C3AED 0%,#9F67F5 100%);
                        height:5px;font-size:0;line-height:0;">&nbsp;</td>
          </tr>

          <!-- Header -->
          <tr>
            <td style="padding:36px 40px 24px;border-bottom:1px solid #F3F0FF;">
              <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td style="vertical-align:middle;">
                    <!-- Logo mark: W letter in brand color -->
                    <div style="display:inline-block;width:36px;height:36px;
                                background:linear-gradient(135deg,#7C3AED,#9F67F5);
                                border-radius:10px;text-align:center;line-height:36px;
                                font-size:20px;font-weight:900;color:#ffffff;
                                font-family:-apple-system,sans-serif;
                                vertical-align:middle;">W</div>
                  </td>
                  <td style="padding-left:12px;vertical-align:middle;">
                    <span style="font-size:18px;font-weight:700;color:#0F0A1E;
                                  letter-spacing:-0.3px;">Wenzap</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 28px;">
              <h1 style="margin:0 0 16px;font-size:24px;font-weight:700;
                          color:#0F0A1E;line-height:1.3;letter-spacing:-0.4px;">
                Confirme seu e-mail
              </h1>
              <p style="margin:0 0 24px;font-size:15px;color:#4B5563;line-height:1.65;">
                Olá, tudo bem?
              </p>
              <p style="margin:0 0 32px;font-size:15px;color:#4B5563;line-height:1.65;">
                Recebemos seu cadastro no Wenzap. Para proteger sua conta e liberar o acesso
                ao seu workspace, confirme seu e-mail clicando no botão abaixo.
              </p>

              <!-- CTA button -->
              <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                <tr>
                  <td align="center" style="padding-bottom:28px;">
                    <a href="{verification_url}"
                       style="display:inline-block;padding:14px 36px;
                              background:linear-gradient(135deg,#7C3AED 0%,#9F67F5 100%);
                              color:#ffffff;text-decoration:none;border-radius:12px;
                              font-size:15px;font-weight:600;letter-spacing:0.1px;
                              mso-padding-alt:0;line-height:1;">
                      Confirmar meu e-mail
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Fallback link -->
              <p style="margin:0 0 20px;font-size:13px;color:#6B7280;line-height:1.6;">
                Se o botão não funcionar, copie e cole este link no seu navegador:
              </p>
              <p style="margin:0 0 28px;word-break:break-all;">
                <a href="{verification_url}"
                   style="font-size:13px;color:#7C3AED;text-decoration:underline;">
                  {verification_url}
                </a>
              </p>

              <!-- Expiry notice -->
              <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                <tr>
                  <td style="background-color:#F9F7FF;border-radius:10px;
                              padding:14px 18px;border-left:3px solid #7C3AED;">
                    <p style="margin:0;font-size:13px;color:#4B5563;line-height:1.5;">
                      &#9200;&nbsp; Este link expira em <strong>24 horas</strong>.
                      Se você não criou uma conta no Wenzap, pode ignorar este e-mail com segurança.
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:20px 40px 32px;border-top:1px solid #F3F0FF;">
              <p style="margin:0;font-size:12px;color:#9CA3AF;line-height:1.6;text-align:center;">
                Wenzap &mdash; Plataforma de Agentes de IA para Empresas<br />
                Você está recebendo este e-mail porque se cadastrou em
                <a href="https://app.wenzap.com.br"
                   style="color:#7C3AED;text-decoration:none;">app.wenzap.com.br</a>.
              </p>
            </td>
          </tr>

        </table>
        <!-- /Card -->

      </td>
    </tr>
  </table>

</body>
</html>"""


def verification_email_text(verification_url: str) -> str:
    return f"""Confirme seu e-mail no Wenzap
=============================

Olá,

Recebemos seu cadastro no Wenzap. Para proteger sua conta e liberar o acesso
ao seu workspace, confirme seu e-mail acessando o link abaixo:

{verification_url}

Este link expira em 24 horas.

Se você não criou uma conta no Wenzap, pode ignorar este e-mail com segurança.

--
Wenzap — Plataforma de Agentes de IA para Empresas
https://app.wenzap.com.br
"""
