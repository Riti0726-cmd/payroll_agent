import { MsalProvider } from "@azure/msal-react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AuthGate } from "./auth/AuthGate";
import { isAuthDisabled, msalInstance } from "./auth/msalConfig";
import { applyTheme, resolveInitialTheme } from "./lib/theme";
import { ThemeProvider } from "./theme/ThemeProvider";
import "./styles/tokens.css";
import "./styles/global.css";
import "./styles/grain.css";
import App from "./App.tsx";

applyTheme(resolveInitialTheme());

const root = createRoot(document.getElementById("root")!);

const tree = (
  <StrictMode>
    <ThemeProvider>
      <AuthGate>
        <App />
      </AuthGate>
    </ThemeProvider>
  </StrictMode>
);

if (isAuthDisabled) {
  root.render(tree);
} else {
  await msalInstance.initialize();
  // Process any pending redirect response before rendering UI.
  await msalInstance.handleRedirectPromise();
  root.render(
    <StrictMode>
      <ThemeProvider>
        <MsalProvider instance={msalInstance}>
          <AuthGate>
            <App />
          </AuthGate>
        </MsalProvider>
      </ThemeProvider>
    </StrictMode>,
  );
}
