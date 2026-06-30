import { LandingHero } from "@/components/LandingHero";
import { MindsetSection } from "@/components/MindsetSection";
import { AgentToolsSection } from "@/components/AgentToolsSection";
import { HowItWorksSection } from "@/components/HowItWorksSection";
import { ChannelsSection } from "@/components/ChannelsSection";
import { IntegrationsRoadmapSection } from "@/components/IntegrationsRoadmapSection";
import { ProductPreviewSection } from "@/components/ProductPreviewSection";
import { SelfUseSection } from "@/components/SelfUseSection";
import { TrustControlSection } from "@/components/TrustControlSection";
import { FinalCTASection } from "@/components/FinalCTASection";

export default function HomePage() {
  return (
    <main>
      <LandingHero />
      <MindsetSection />
      <AgentToolsSection />
      <HowItWorksSection />
      <ChannelsSection />
      <IntegrationsRoadmapSection />
      <ProductPreviewSection />
      <SelfUseSection />
      <TrustControlSection />
      <FinalCTASection />
    </main>
  );
}
