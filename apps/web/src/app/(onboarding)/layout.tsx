export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-nb-bg flex flex-col">
      {children}
    </div>
  );
}
