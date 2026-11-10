import * as React from "react";
import { config } from "../config";
import { apiScopes, getAuthClient, graphMailScopes, supportsNaa, type SignedInUser } from "./naa";

type Status = "loading" | "signedOut" | "signedIn" | "error";

interface SpecialistContextValue {
  status: Status;
  user: SignedInUser | null;
  error: string | null;
  signIn: () => Promise<void>;
  /** Token for the payroll API (undefined when auth is disabled). */
  getAccessToken: () => Promise<string | undefined>;
  /** Delegated Graph Mail.Read token, required by /triage/stream. */
  getGraphAccessToken: () => Promise<string | undefined>;
}

const SpecialistContext = React.createContext<SpecialistContextValue | null>(null);

export function SpecialistProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = React.useState<Status>("loading");
  const [user, setUser] = React.useState<SignedInUser | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const acquire = React.useCallback(async (scopes: string[]) => {
    const result = await getAuthClient().getToken(scopes);
    if (result.user) {
      setUser(result.user);
      setStatus("signedIn");
    }
    return result.accessToken || undefined;
  }, []);

  const signIn = React.useCallback(async () => {
    setError(null);
    setStatus("loading");
    try {
      await acquire(apiScopes);
      setStatus("signedIn");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStatus("error");
    }
  }, [acquire]);

  React.useEffect(() => {
    // NAA (and local no-auth) sign in silently; the dialog fallback waits for a click.
    if (config.authDisabled || supportsNaa()) void signIn();
    else setStatus("signedOut");
  }, [signIn]);

  const value = React.useMemo<SpecialistContextValue>(
    () => ({
      status,
      user,
      error,
      signIn,
      getAccessToken: () => acquire(apiScopes),
      getGraphAccessToken: () => acquire(graphMailScopes),
    }),
    [status, user, error, signIn, acquire],
  );

  return <SpecialistContext.Provider value={value}>{children}</SpecialistContext.Provider>;
}

export function useSpecialist(): SpecialistContextValue {
  const ctx = React.useContext(SpecialistContext);
  if (!ctx) throw new Error("useSpecialist must be used inside SpecialistProvider");
  return ctx;
}
