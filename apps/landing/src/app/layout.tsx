import type { Metadata } from "next";
import "./globals.css";
import { LandingHeader } from "@/components/LandingHeader";
import { LandingFooter } from "@/components/LandingFooter";
import { WenzapWidgetScript } from "@/components/WenzapWidgetScript";
import { LandingTracker } from "@/components/LandingTracker";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://wenzap.com.br";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "Wenzap — Coloque agentes de IA para trabalhar na sua operação",
  description:
    "O Wenzap ajuda empresas a atender clientes, organizar conversas e automatizar partes do atendimento e vendas com agentes de IA — sem tirar sua equipe do controle.",
  keywords: [
    "agentes de IA para empresas",
    "atendimento com IA",
    "automação de atendimento",
    "WhatsApp com IA",
    "agente de vendas IA",
    "chatbot empresarial",
    "Wenzap",
  ],
  alternates: {
    canonical: SITE_URL,
  },
  openGraph: {
    type: "website",
    url: SITE_URL,
    title: "Wenzap — Coloque agentes de IA para trabalhar na sua operação",
    description:
      "O Wenzap ajuda empresas a atender clientes, organizar conversas e automatizar partes do atendimento e vendas com agentes de IA — sem tirar sua equipe do controle.",
    siteName: "Wenzap",
    images: [
      {
        url: `${SITE_URL}/og-image.svg`,
        width: 1200,
        height: 630,
        alt: "Wenzap — Agentes de IA para atendimento, vendas e relacionamento",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Wenzap — Coloque agentes de IA para trabalhar na sua operação",
    description:
      "Atenda clientes, organize conversas e automatize partes do atendimento e vendas — sem tirar sua equipe do controle.",
    images: [`${SITE_URL}/og-image.svg`],
  },
  robots: {
    index: true,
    follow: true,
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Wenzap",
  applicationCategory: "BusinessApplication",
  description:
    "Plataforma de agentes de IA para atendimento, vendas e relacionamento com clientes.",
  url: SITE_URL,
  offers: {
    "@type": "Offer",
    price: "0",
    priceCurrency: "BRL",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body>
        <LandingTracker />
        <LandingHeader />
        {children}
        <LandingFooter />
        <WenzapWidgetScript />
      </body>
    </html>
  );
}
