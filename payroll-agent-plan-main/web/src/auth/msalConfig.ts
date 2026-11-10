import { LogLevel, PublicClientApplication, type Configuration } from "@azure/msal-browser";

/** When true, skip Microsoft sign-in (automated UI tests only). */
export const isAuthDisabled =
  String(import.meta.env.VITE_AUTH_DISABLED ?? "").toLowerCase() === "true";

const clientId = import.meta.env.VITE_ENTRA_CLIENT_ID ?? "";
const tenantId = import.meta.env.VITE_ENTRA_TENANT_ID || "common";
/** MSAL Browser v5: dedicated redirect-bridge page (not the React SPA root). */
const defaultRedirectUri = `${window.location.origin}/redirect.html`;
const redirectUri =
  (import.meta.env.VITE_ENTRA_REDIRECT_URI as string | undefined)?.trim() ||
  defaultRedirectUri;
const apiScope = import.meta.env.VITE_ENTRA_API_SCOPE as string | undefined;

export const isMsalConfigured = !isAuthDisabled && Boolean(clientId.trim());

export const msalConfig: Configuration = {
  auth: {
    clientId: clientId || "00000000-0000-0000-0000-000000000000",
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri,
  },
  cache: { cacheLocation: "localStorage" },
  system: {
    loggerOptions: {
      logLevel: LogLevel.Warning,
    },
  },
};

/** Sign-in / general API scopes (Foundry invoke if scoped separately). */
export const loginRequest = {
  scopes: apiScope ? [apiScope] : ["openid", "profile", "email"],
};

/** Delegated Graph mail — used for TRIAGE_RUN (no client secret). */
export const graphMailRequest = {
  scopes: ["https://graph.microsoft.com/Mail.Read"],
};

export const msalInstance = new PublicClientApplication(msalConfig);
