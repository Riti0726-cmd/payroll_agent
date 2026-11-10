import { AuthenticatedTemplate, UnauthenticatedTemplate, useMsal } from "@azure/msal-react";
import type { ReactNode } from "react";
import { LoginPage } from "../pages/LoginPage";
import { isAuthDisabled } from "./msalConfig";

type AuthGateProps = {
  children: ReactNode;
};

export function AuthGate({ children }: AuthGateProps) {
  if (isAuthDisabled) {
    return <>{children}</>;
  }

  return <MsalAuthGate>{children}</MsalAuthGate>;
}

function MsalAuthGate({ children }: AuthGateProps) {
  const { inProgress } = useMsal();
  const isLoading = inProgress === "startup" || inProgress === "handleRedirect";

  return (
    <>
      <AuthenticatedTemplate>{children}</AuthenticatedTemplate>
      <UnauthenticatedTemplate>
        <LoginPage isLoading={isLoading} />
      </UnauthenticatedTemplate>
    </>
  );
}
