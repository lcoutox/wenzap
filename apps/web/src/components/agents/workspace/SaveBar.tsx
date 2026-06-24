export function SaveBar({
  saving,
  saveError,
  saveSuccess,
}: {
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
}) {
  return (
    <div className="flex items-center justify-end gap-3 pt-2">
      {saveError   && <p className="text-sm text-nb-danger flex-1">{saveError}</p>}
      {saveSuccess && <p className="text-sm text-nb-success flex-1">Salvo com sucesso.</p>}
      <button
        type="submit"
        disabled={saving}
        className="px-5 py-2 bg-nb-primary text-white text-sm font-medium rounded-xl hover:bg-nb-primary-strong disabled:opacity-40 transition-colors"
      >
        {saving ? "Salvando..." : "Salvar alterações"}
      </button>
    </div>
  );
}
