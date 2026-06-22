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
      {saveError && <p className="text-sm text-red-500 flex-1">{saveError}</p>}
      {saveSuccess && <p className="text-sm text-green-600 flex-1">Salvo com sucesso.</p>}
      <button
        type="submit"
        disabled={saving}
        className="px-5 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
      >
        {saving ? "Salvando..." : "Salvar alterações"}
      </button>
    </div>
  );
}
