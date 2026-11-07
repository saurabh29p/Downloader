/** After a media or file error: did the sign-in expire? (Then show "Sign in again".) */
export async function signedOut(): Promise<boolean> {
  try {
    const response = await fetch("/api/auth/me", { credentials: "same-origin" });
    if (!response.ok) return false;
    const me = (await response.json()) as { signed_in?: boolean; login_required?: boolean };
    return !!me.login_required && !me.signed_in;
  } catch {
    return false; // offline: the error message covers it
  }
}
