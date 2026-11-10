// Fallback sign-in page, opened with Office.context.ui.displayDialogAsync when the host
// does not support Nested App Authentication. Redirects to Entra and back to this page,
// then sends the token to the task pane with messageParent.
import { PublicClientApplication } from "@azure/msal-browser";
import { config } from "../config";
import { userFromAccount } from "./naa";

function send(message: Record<string, unknown>): void {
  Office.context.ui.messageParent(JSON.stringify(message));
}

async function run(): Promise<void> {
  const params = new URLSearchParams(window.location.search);
  const scopeParam = params.get("scopes") || sessionStorage.getItem("addin.scopes") || "";
  const scopes = scopeParam.split(" ").filter(Boolean);
  sessionStorage.setItem("addin.scopes", scopeParam);

  const pca = new PublicClientApplication({
    auth: {
      clientId: config.clientId,
      authority: `https://login.microsoftonline.com/${config.tenantId}`,
      redirectUri: `${window.location.origin}/dialog.html`,
    },
    cache: { cacheLocation: "sessionStorage" },
  });
  await pca.initialize();

  const redirect = await pca.handleRedirectPromise();
  const account = redirect?.account ?? pca.getAllAccounts()[0];
  if (!account) {
    await pca.loginRedirect({ scopes });
    return;
  }
  const result = await pca.acquireTokenSilent({ scopes, account });
  const user = userFromAccount(result.account ?? account);
  send({
    accessToken: result.accessToken,
    expiresOn: result.expiresOn?.getTime(),
    specialistId: user?.specialistId,
    displayName: user?.displayName,
  });
}

Office.onReady(() => {
  run().catch((error: unknown) => {
    send({ error: error instanceof Error ? error.message : String(error) });
  });
});
