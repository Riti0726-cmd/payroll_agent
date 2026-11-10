/** Build-time public settings, inlined by webpack DefinePlugin (see webpack.config.js). */

type AddinEnv = Partial<
  Record<
    | "VITE_AUTH_DISABLED"
    | "VITE_ENTRA_CLIENT_ID"
    | "VITE_ENTRA_TENANT_ID"
    | "VITE_ENTRA_API_SCOPE"
    | "VITE_API_BASE_URL"
    | "VITE_QUEUE_MAILBOX"
    | "VITE_DEV_SPECIALIST_ID",
    string
  >
>;

declare const __ADDIN_ENV__: AddinEnv;

const env: AddinEnv = typeof __ADDIN_ENV__ === "undefined" ? {} : __ADDIN_ENV__;

export const config = {
  authDisabled: (env.VITE_AUTH_DISABLED ?? "").toLowerCase() === "true",
  clientId: (env.VITE_ENTRA_CLIENT_ID ?? "").trim(),
  tenantId: (env.VITE_ENTRA_TENANT_ID ?? "").trim() || "common",
  apiScope: (env.VITE_ENTRA_API_SCOPE ?? "").trim(),
  apiBaseUrl: ((env.VITE_API_BASE_URL ?? "").trim() || "/api").replace(/\/$/, ""),
  mailboxOverride: (env.VITE_QUEUE_MAILBOX ?? "").trim(),
  devSpecialistId: (env.VITE_DEV_SPECIALIST_ID ?? "").trim() || "default",
};

/** Absolute URL for a backend path (works for relative "/api" and absolute bases). */
export function apiUrl(path: string): URL {
  return new URL(`${config.apiBaseUrl}${path}`, window.location.origin);
}
