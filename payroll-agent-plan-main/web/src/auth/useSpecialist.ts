import { InteractionRequiredAuthError } from "@azure/msal-browser";
import { useMsal } from "@azure/msal-react";
import { useCallback } from "react";
import { graphMailRequest, isAuthDisabled, loginRequest } from "./msalConfig";

type SpecialistClaims = {
  oid?: string;
  preferred_username?: string;
};

const localSpecialist = {
  specialistId: "default",
  displayName: "Local specialist",
  getAccessToken: async () => undefined as string | undefined,
  getGraphAccessToken: async () => undefined as string | undefined,
  signOut: async () => undefined,
};

export function useSpecialist(): {
  specialistId: string;
  displayName: string;
  getAccessToken: () => Promise<string | undefined>;
  getGraphAccessToken: () => Promise<string | undefined>;
  signOut: () => Promise<void>;
} {
  if (isAuthDisabled) {
    return localSpecialist;
  }

  // eslint-disable-next-line react-hooks/rules-of-hooks -- isAuthDisabled is fixed per Vite env load
  return useMsalSpecialist();
}

function useMsalSpecialist(): {
  specialistId: string;
  displayName: string;
  getAccessToken: () => Promise<string | undefined>;
  getGraphAccessToken: () => Promise<string | undefined>;
  signOut: () => Promise<void>;
} {
  const { accounts, instance } = useMsal();
  const account = accounts[0];
  const claims = account?.idTokenClaims as SpecialistClaims | undefined;
  const specialistId = claims?.preferred_username || claims?.oid || account?.username || "default";
  const displayName = account?.name || account?.username || "Payroll Specialist";

  const acquire = useCallback(
    async (scopes: string[]) => {
      if (!account) {
        return undefined;
      }
      const request = { scopes, account };
      try {
        const response = await instance.acquireTokenSilent(request);
        return response.accessToken;
      } catch (error) {
        if (error instanceof InteractionRequiredAuthError) {
          const response = await instance.acquireTokenPopup(request);
          return response.accessToken;
        }
        throw error;
      }
    },
    [account, instance],
  );

  const getAccessToken = useCallback(async () => acquire(loginRequest.scopes), [acquire]);

  /** Delegated Graph Mail.Read token for triage (option 2). */
  const getGraphAccessToken = useCallback(
    async () => acquire(graphMailRequest.scopes),
    [acquire],
  );

  const signOut = useCallback(async () => {
    await instance.logoutPopup({ account: account ?? undefined });
  }, [account, instance]);

  return { specialistId, displayName, getAccessToken, getGraphAccessToken, signOut };
}
