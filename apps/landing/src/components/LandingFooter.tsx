export function LandingFooter() {
  return (
    <footer className="border-t border-nb-border bg-nb-surface">
      <div className="max-w-6xl mx-auto px-4 py-10 flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-nb-muted">
        <p>© {new Date().getFullYear()} Wenzap. Todos os direitos reservados.</p>
        <p>Tecnologia para operar com IA de verdade.</p>
      </div>
    </footer>
  );
}
