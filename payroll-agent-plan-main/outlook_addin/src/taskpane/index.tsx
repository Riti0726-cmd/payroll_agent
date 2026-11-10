import * as React from "react";
import { createRoot } from "react-dom/client";
import "../styles/tokens.css";
import "../styles/global.css";
import "../styles/grain.css";
import App from "./components/App";
import { SpecialistProvider } from "../auth/useSpecialist";
import { ThemeProvider, resolveInitialTheme } from "../theme/theme";
import { TriageRunProvider } from "./triage/TriageRunContext";

/* global document, Office, module, require, HTMLElement */

const rootElement: HTMLElement | null = document.getElementById("container");
const root = rootElement ? createRoot(rootElement) : undefined;

function render(AppComponent: typeof App) {
  root?.render(
    <ThemeProvider>
      <SpecialistProvider>
        <TriageRunProvider>
          <AppComponent />
        </TriageRunProvider>
      </SpecialistProvider>
    </ThemeProvider>
  );
}

/* Render application after Office initializes */
Office.onReady(() => {
  // Set the theme before first paint so the pane doesn't flash the wrong palette.
  document.documentElement.dataset.theme = resolveInitialTheme();
  render(App);
});

if ((module as any).hot) {
  (module as any).hot.accept("./components/App", () => {
    render(require("./components/App").default);
  });
}
