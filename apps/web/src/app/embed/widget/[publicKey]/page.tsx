"use client";

import { useParams } from "next/navigation";
import { WidgetEmbed } from "@/components/widget/WidgetEmbed";

export default function EmbedWidgetPage() {
  const params = useParams();
  const publicKey = params.publicKey as string;

  if (!publicKey) return null;

  return <WidgetEmbed publicKey={publicKey} />;
}
