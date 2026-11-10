import { useMsal } from "@azure/msal-react";
import { useState } from "react";
import { isMsalConfigured, loginRequest } from "../auth/msalConfig";
import { ThemeToggle } from "../components/ThemeToggle";
import styles from "./LoginPage.module.css";

type LoginPageProps = {
  isLoading?: boolean;
};

export function LoginPage({ isLoading = false }: LoginPageProps) {
  const { instance } = useMsal();
  const [message, setMessage] = useState<string | undefined>(
    isMsalConfigured ? undefined : "Add VITE_ENTRA_CLIENT_ID to enable Microsoft sign-in.",
  );

  const handleSignIn = async () => {
    if (!isMsalConfigured) {
      setMessage("Microsoft sign-in is not configured. Set VITE_ENTRA_CLIENT_ID and restart Vite.");
      return;
    }

    setMessage(undefined);

    try {
      await instance.loginPopup(loginRequest);
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unable to start Microsoft sign-in.";
      setMessage(detail);
    }
  };

  return (
    <main className={styles.loginPage}>
      <div className={styles.themeSlot}>
        <ThemeToggle />
      </div>
      <section className={styles.panel} aria-labelledby="login-title">
        <div className={styles.brandRail} aria-hidden="true">
          <span />
          <span />
          <span />
        </div>

        <div className={styles.content}>
          <p className={styles.eyebrow}>Industrial payroll operations</p>
          <h1 id="login-title">Payroll Specialist</h1>
          <p className={styles.copy}>
            Sign in with Microsoft to review payroll queues, draft specialist actions, and keep
            operational context tied to your Entra identity.
          </p>

          <button className="btn-primary" type="button" onClick={handleSignIn} disabled={isLoading}>
            {isLoading ? "Preparing sign-in..." : "Sign in with Microsoft"}
          </button>

          {message ? (
            <p className={styles.notice} role="status">
              {message}
            </p>
          ) : null}
        </div>
      </section>
    </main>
  );
}
