/**
 * Embed layout — no auth, no sidebar, transparent body.
 * Overrides the dark background set in globals.css so the widget iframe
 * is transparent outside the launcher and chat window areas.
 */
export default function EmbedLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {/* Override globals.css body background so the iframe area is transparent. */}
      <style>{`html, body { background: transparent !important; }`}</style>
      {children}
    </>
  );
}
