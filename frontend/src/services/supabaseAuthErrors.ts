type AuthAction = "login" | "register";

export function supabaseAuthErrorMessage(error: unknown, action: AuthAction): string | null {
  const code = typeof error === "object" && error !== null && "code" in error
    ? String(error.code)
    : "";
  const message = error instanceof Error ? error.message.toLowerCase() : "";

  if (["user_already_exists", "email_exists"].includes(code) || message.includes("already registered")) {
    return "An account with this email already exists.";
  }
  if (["invalid_credentials", "invalid_grant", "user_not_found"].includes(code)) {
    return "Invalid email or password.";
  }
  if (code === "weak_password" || message.includes("password should be at least")) {
    return "Choose a stronger password with at least 8 characters.";
  }
  if (["email_address_invalid", "validation_failed"].includes(code)) {
    return action === "register" ? "Enter a valid email address." : "Invalid email or password.";
  }
  if (["over_email_send_rate_limit", "over_request_rate_limit", "email_rate_limit_exceeded"].includes(code)) {
    return "Too many attempts. Wait a moment, then try again.";
  }
  if (message.includes("fetch") || message.includes("network")) {
    return "Supabase Authentication is unavailable. Check your connection and try again.";
  }
  return null;
}