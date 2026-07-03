export function LandingFooter() {
  return (
    <footer className="border-t border-nb-border bg-nb-surface">
      <div className="max-w-6xl mx-auto px-4 py-10 flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-nb-muted">
        <div className="flex flex-col gap-1 text-center md:text-left">
          <p>© {new Date().getFullYear()} Wenzap. Todos os direitos reservados.</p>
          <p>Wenzap é uma plataforma operada por <span className="text-nb-secondary">ORBIT HUB SOFTWARE LTDA</span> — CNPJ 54.414.617/0001-82</p>
        </div>
        <p>Tecnologia para operar com IA de verdade.</p>
      </div>
    </footer>
  );
}
