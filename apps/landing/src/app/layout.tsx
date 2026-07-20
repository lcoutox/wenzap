import type { Metadata } from "next";
import "./globals.css";
import { LandingHeader } from "@/components/LandingHeader";
import { LandingFooter } from "@/components/LandingFooter";
import { WenzapWidgetScript } from "@/components/WenzapWidgetScript";
import { LandingTracker } from "@/components/LandingTracker";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://wenzap.com.br";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "Wenzap — Agentes de IA que qualificam, agendam e vendem no WhatsApp",
  description:
    "Responder rápido não vende. O Wenzap qualifica o lead, agenda a visita e faz o follow-up sozinho no WhatsApp e no seu site. Você vê cada passo e assume quando quiser.",
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
    title: "Wenzap — Agentes de IA que qualificam, agendam e vendem no WhatsApp",
    description:
      "Responder rápido não vende. O Wenzap qualifica o lead, agenda a visita e faz o follow-up sozinho no WhatsApp e no seu site. Você vê cada passo e assume quando quiser.",
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
    title: "Wenzap — Agentes de IA que qualificam, agendam e vendem no WhatsApp",
    description:
      "Responder rápido não vende. O agente qualifica, agenda a visita e faz o follow-up sozinho — e você vê cada passo e assume quando quiser.",
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
