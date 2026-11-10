import * as React from "react";
import { useSpecialist } from "../../auth/useSpecialist";
import { useCurrentItem } from "../hooks/useCurrentItem";
import { useTriageRun, type TriageLiveStatus } from "../triage/TriageRunContext";
import styles from "./App.module.css";
import { EmailTab } from "./EmailTab";
import { QaChat } from "./QaChat";
import { QueueList } from "./QueueList";
import { EmptyState, ErrorBox, InlineNote } from "./ui/Feedback";
import { ThemeToggle } from "./ui/ThemeToggle";

type TabId = "email" | "ask" | "queue";

const TABS: { id: TabId; label: string }[] = [
  { id: "email", label: "This email" },
  { id: "ask", label: "Ask" },
  { id: "queue", label: "Queue" },
];

/** Port of the web AppShell TriageStatusPill. */
function TriageStatusPill({ status }: { status: TriageLiveStatus }) {
  if (status.phase === "idle") return null;
  if (status.phase === "running") {
    const progress = status.total ? `${status.index}/${status.total}` : "";
    return (
      <div aria-live="polite" className={`${styles.triagePill} ${styles.triagePillLive}`}>
        <span className={styles.triageDot} aria-hidden />
        <span className={styles.triageLabel}>Triage {progress}</span>
        <span className={styles.triageDetail}>{status.subject}</span>
      </div>
    );
  }
  if (status.phase === "done") {
    return (
      <div aria-live="polite" className={`${styles.triagePill} ${styles.triagePillDone}`}>
        <span className={styles.triageLabel}>Triage complete</span>
        <span className={styles.triageDetail}>
          {status.succeeded} done · {status.failed} failed · {status.skipped} skipped
        </span>
      </div>
    );
  }
  return (
    <div aria-live="polite" className={`${styles.triagePill} ${styles.triagePillError}`}>
      <span className={styles.triageLabel}>Triage failed</span>
      <span className={styles.triageDetail}>{status.message}</span>
    </div>
  );
}

export default function App() {
  const { status, user, error, signIn } = useSpecialist();
  const triage = useTriageRun();
  const item = useCurrentItem();
  const [tab, setTab] = React.useState<TabId>("email");
  const signedIn = status === "signedIn" && Boolean(user);

  let content: React.ReactNode;
  if (status === "loading") {
    content = <InlineNote kicker="Signing in">Connecting to your Microsoft 365 account…</InlineNote>;
  } else if (!signedIn) {
    content = (
      <EmptyState
        kicker="Sign in"
        title="Connect your specialist account"
        detail="Sign in with your Engage PEO Microsoft account to load triage results for your mailbox."
      >
        <ErrorBox label="Sign-in failed" message={error} />
        <button className="btn-primary" type="button" onClick={() => void signIn()}>
          Sign in
        </button>
      </EmptyState>
    );
  } else if (tab === "email") {
    content = <EmailTab item={item} />;
  } else if (tab === "ask") {
    content = <QaChat item={item} />;
  } else {
    content = <QueueList />;
  }

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.headerRow}>
          <div className={styles.identity}>
            <span className={styles.brand}>Payroll Specialist</span>
            {user ? <span className={styles.displayName}>{user.displayName}</span> : null}
          </div>
          <ThemeToggle />
        </div>
        <TriageStatusPill status={triage.status} />
        <nav className={styles.nav} aria-label="Sections">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={tab === t.id ? `${styles.navLink} ${styles.active}` : styles.navLink}
              aria-current={tab === t.id ? "page" : undefined}
              disabled={!signedIn}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main className={styles.content} key={tab}>
        {content}
      </main>
    </div>
  );
}
