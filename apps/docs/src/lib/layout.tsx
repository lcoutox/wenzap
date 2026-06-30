import type { BaseLayoutProps } from "fumadocs-ui/layouts/shared";
import { WenzapLogo } from "@/components/WenzapLogo";

export function baseOptions(): BaseLayoutProps {
  return {
    nav: {
      title: <WenzapLogo />,
    },
    links: [
      {
        text: "Produto",
        url: "http://localhost:3000/dashboard",
        external: true,
      },
      {
        text: "Landing",
        url: "http://127.0.0.1:3001",
        external: true,
      },
    ],
  };
}
