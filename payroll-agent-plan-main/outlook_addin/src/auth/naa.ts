// Sign-in for the task pane.
// 1) Nested App Authentication (MSAL NAA): silent SSO with the account signed in to Outlook.
// 2) Fallback for hosts without NAA: MSAL redirect inside an Office dialog (dialog.html).
import {
  createNestablePublicClientApplication,
  type AccountInfo,
  type IPublicClientApplication,
} from "@azure/msal-browser";
import { config } from "../config";

/** Same scopes as web/src/auth/msalConfig.ts. */
export const apiScopes = config.apiScope ? [config.apiScope] : ["openid", "profile", "email"];
export const graphMailScopes = ["https://graph.microsoft.com/Mail.Read"];

export interface SignedInUser {
  specialistId: string;
  displayName: string;
}

type Claims = { preferred_username?: string; oid?: string; name?: string };

/** Mirrors web/src/auth/useSpecialist.ts: preferred_username, then oid, then username. */
export function userFromAccount(account: AccountInfo | null | undefined): SignedInUser | null {
  if (!account) return null;
  const claims = (account.idTokenClaims ?? {}) as Claims;
  return {
    specialistId: claims.preferred_username || claims.oid || account.username || "default",
    displayName: account.name || claims.name || account.username || "Payroll Specialist",
  };
}

export interface TokenResult {
  accessToken: string;
  user: SignedInUser | null;
}

export interface AuthClient {
  getToken(scopes: string[]): Promise<TokenResult>;
}

const authority = () => `https://login.microsoftonline.com/${config.tenantId}`;

export function supportsNaa(): boolean {
  try {
    return Boolean(Office.context.requirements?.isSetSupported("NestedAppAuth", "1.1"));
  } catch {
    return false;
  }
}

class NaaClient implements AuthClient {
  private pca: Promise<IPublicClientApplication>;

  constructor() {
    this.pca = createNestablePublicClientApplication({
      auth: { clientId: config.clientId, authority: authority() },
    });
  }

  async getToken(scopes: string[]): Promise<TokenResult> {
    const pca = await this.pca;
    const account = pca.getActiveAccount() ?? pca.getAllAccounts()[0];
    const request = account ? { scopes, account } : { scopes };
    let result;
    try {
      result = await pca.acquireTokenSilent(request);
    } catch {
      // Consent or interaction required: NAA shows the host's own prompt.
      result = await pca.acquireTokenPopup({ scopes });
    }
    if (result.account) pca.setActiveAccount(result.account);
    return { accessToken: result.accessToken, user: userFromAccount(result.account) };
  }
}

interface DialogMessage {
  accessToken?: string;
  expiresOn?: number;
  specialistId?: string;
  displayName?: string;
  error?: string;
}

class DialogClient implements AuthClient {
  private cache = new Map<
    string,
    { token: string; expiresOn: number; user: SignedInUser | null }
  >();

  async getToken(scopes: string[]): Promise<TokenResult> {
    const key = scopes.join(" ");
    const cached = this.cache.get(key);
    if (cached && cached.expiresOn - Date.now() > 5 * 60 * 1000) {
      return { accessToken: cached.token, user: cached.user };
    }
    const message = await this.openDialog(scopes);
    if (!message.accessToken) throw new Error(message.error || "Sign-in was cancelled.");
    const user = message.specialistId
      ? {
          specialistId: message.specialistId,
          displayName: message.displayName || message.specialistId,
        }
      : null;
    this.cache.set(key, {
      token: message.accessToken,
      expiresOn: message.expiresOn ?? Date.now() + 30 * 60 * 1000,
      user,
    });
    return { accessToken: message.accessToken, user };
  }

  private openDialog(scopes: string[]): Promise<DialogMessage> {
    const url = new URL("dialog.html", window.location.href);
    url.searchParams.set("scopes", scopes.join(" "));
    return new Promise((resolve, reject) => {
      Office.context.ui.displayDialogAsync(url.toString(), { height: 60, width: 30 }, (result) => {
        if (result.status !== Office.AsyncResultStatus.Succeeded) {
          reject(new Error(result.error?.message ?? "Could not open the sign-in dialog."));
          return;
        }
        const dialog = result.value;
        dialog.addEventHandler(Office.EventType.DialogMessageReceived, (arg) => {
          dialog.close();
          try {
            resolve(JSON.parse((arg as { message: string }).message) as DialogMessage);
          } catch {
            reject(new Error("Invalid sign-in response."));
          }
        });
        dialog.addEventHandler(Office.EventType.DialogEventReceived, () => {
          reject(new Error("Sign-in was cancelled."));
        });
      });
    });
  }
}

class DisabledClient implements AuthClient {
  async getToken(): Promise<TokenResult> {
    return {
      accessToken: "",
      user: { specialistId: config.devSpecialistId, displayName: "Local specialist" },
    };
  }
}

let client: AuthClient | null = null;

export function getAuthClient(): AuthClient {
  if (!client) {
    if (config.authDisabled) client = new DisabledClient();
    else if (!config.clientId) throw new Error("VITE_ENTRA_CLIENT_ID is not set for the add-in.");
    else client = supportsNaa() ? new NaaClient() : new DialogClient();
  }
  return client;
}

/** Test hook. */
export function setAuthClient(next: AuthClient | null): void {
  client = next;
}
