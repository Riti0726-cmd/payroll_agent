import { useEffect, useRef } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { ThemeToggle } from "../components/ThemeToggle";
import { Toast } from "../components/Toast";
import { useSpecialist } from "../auth/useSpecialist";
import { animateEnter } from "../lib/animateEnter";
import { TriageRunProvider, useTriageRun } from "../triage/TriageRunContext";
import styles from "./AppShell.module.css";

const navItems = [
  { to: "/queue", label: "Queue" },
  { to: "/drafts", label: "Drafts" },
  { to: "/qa", label: "Q&A" },
  { to: "/change-lists", label: "Change lists" },
  { to: "/history", label: "History" },
  { to: "/settings", label: "Settings" },
];

function TriageStatusPill() {
  const { status } = useTriageRun();

  if (status.phase === "idle") {
    return null;
  }

  if (status.phase === "running") {
    const progress =
      status.total > 0 ? `${status.index}/${status.total}` : "…";
    const detail = status.category
      ? `${status.category} · ${status.subject}`
      : status.subject;
    return (
      <div
        aria-live="polite"
        className={`${styles.triagePill} ${styles.triagePillLive}`}
        title={detail}
      >
        <span className={styles.triageDot} aria-hidden />
        <span className={styles.triageLabel}>Triage {progress}</span>
        <span className={styles.triageDetail}>{detail}</span>
      </div>
    );
  }

  if (status.phase === "done") {
    return (
      <div aria-live="polite" className={`${styles.triagePill} ${styles.triagePillDone}`}>
        <span className={styles.triageLabel}>
          Done · {status.succeeded} ok
          {status.failed ? ` · ${status.failed} failed` : ""}
        </span>
      </div>
    );
  }

  return (
    <div aria-live="polite" className={`${styles.triagePill} ${styles.triagePillError}`}>
      <span className={styles.triageLabel}>Triage failed</span>
    </div>
  );
}

function AppShellInner() {
  const { displayName } = useSpecialist();
  const { isRunning, startTriage, toast, setToast } = useTriageRun();
  const location = useLocation();
  const contentRef = useRef<HTMLElement>(null);

  useEffect(() => {
    animateEnter(contentRef.current);
  }, [location.pathname]);

  useEffect(() => {
    if (!toast) {
      return undefined;
    }

    const timeout = window.setTimeout(() => setToast(null), 8000);
    return () => window.clearTimeout(timeout);
  }, [toast, setToast]);

  return (
    <div className={styles.shell}>
      <aside className={styles.rail} data-enter>
        <div className={styles.brand}>Payroll Specialist</div>
        <nav aria-label="Primary" className={styles.nav}>
          {navItems.map((item) => (
            <NavLink
              className={({ isActive }) =>
                isActive ? `${styles.navLink} ${styles.active}` : styles.navLink
              }
              key={item.to}
              to={item.to}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className={styles.main}>
        <header className={styles.header} data-enter>
          <h1>Payroll Specialist</h1>
          <div className={styles.actions}>
            <TriageStatusPill />
            <ThemeToggle />
            <div className={styles.specialist}>
              <span className={styles.label}>Specialist</span>
              <span className={styles.displayName}>{displayName}</span>
            </div>
            <button
              className="btn-primary"
              type="button"
              onClick={() => void startTriage()}
              disabled={isRunning}
            >
              {isRunning ? "Running triage" : "Run triage"}
            </button>
          </div>
        </header>

        <main className={styles.content} ref={contentRef}>
          <Outlet />
        </main>
      </div>

      <Toast message={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}

export function AppShell() {
  return (
    <TriageRunProvider>
      <AppShellInner />
    </TriageRunProvider>
  );
}
