interface ClerkError {
  code?: string;
  message?: string;
}

export function clerkErrorMessage(errors: ClerkError[]): string {
  const code = errors[0]?.code ?? "";

  switch (code) {
    case "form_password_incorrect":
    case "form_identifier_not_found":
    case "invalid_credentials":
      return "E-mail ou senha inválidos.";

    case "form_identifier_exists":
    case "identifier_already_signed_in":
      return "Já existe uma conta com esse e-mail.";

    case "form_password_length_too_short":
      return "A senha deve ter pelo menos 8 caracteres.";

    case "form_password_pwned":
      return "Essa senha foi comprometida em vazamentos. Escolha outra.";

    case "form_param_format_invalid":
    case "form_param_nil":
      return "E-mail inválido.";

    case "too_many_requests":
      return "Muitas tentativas. Aguarde um momento e tente novamente.";

    case "verification_failed":
      return "Código inválido. Verifique e tente novamente.";

    case "verification_expired":
      return "Código expirado. Solicite um novo código.";

    case "not_allowed_access":
      return "Acesso não autorizado.";

    default:
      return "Não foi possível continuar. Tente novamente.";
  }
}

export function isClerkError(err: unknown): err is { errors: ClerkError[] } {
  return (
    typeof err === "object" &&
    err !== null &&
    "errors" in err &&
    Array.isArray((err as { errors: unknown }).errors)
  );
}
