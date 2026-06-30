import type { Metadata } from "next";
import { RootProvider } from "fumadocs-ui/provider/next";
import "./global.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://docs.wenzap.com.br"),
  title: {
    default: "Wenzap Docs",
    template: "%s | Wenzap Docs",
  },
  description: "Documentação do Wenzap para configurar agentes, operações e integrações.",
  applicationName: "Wenzap Docs",
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <body>
        <RootProvider
          search={{
            enabled: false,
          }}
          theme={{
            enabled: false,
          }}
        >
          {children}
        </RootProvider>
      </body>
    </html>
  );
}
