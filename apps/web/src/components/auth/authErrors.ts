import { ApiError } from "@/lib/api";

export function authErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    switch (err.status) {
      case 401:
        return "E-mail ou senha inválidos.";
      case 409:
        return "Este e-mail já está cadastrado. Faça login para continuar.";
      case 422:
        return err.message || "Verifique os dados informados.";
      default:
        return "Não foi possível concluir. Tente novamente.";
    }
  }
  return "Não foi possível concluir. Tente novamente.";
}
