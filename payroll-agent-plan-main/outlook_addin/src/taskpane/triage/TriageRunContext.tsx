// Port of web/src/triage/TriageRunContext.tsx: one triage run shared across tabs,
// surfaced as the header status pill.
import * as React from "react";
import { runTriage } from "../../api/streams";
import { useSpecialist } from "../../auth/useSpecialist";

export type TriageLiveStatus =
  | { phase: "idle" }
  | { phase: "running"; index: number; total: number; subject: string }
  | { phase: "done"; succeeded: number; failed: number; skipped: number }
  | { phase: "error"; message: string };

interface TriageRunContextValue {
  status: TriageLiveStatus;
  isRunning: boolean;
  /** Increments after each finished run so views can reload. */
  runCount: number;
  startTriage: () => Promise<void>;
}

const TriageRunContext = React.createContext<TriageRunContextValue | null>(null);

export function TriageRunProvider({ children }: { children: React.ReactNode }) {
  const { user, getGraphAccessToken } = useSpecialist();
  const [status, setStatus] = React.useState<TriageLiveStatus>({ phase: "idle" });
  const [runCount, setRunCount] = React.useState(0);
  const running = React.useRef(false);
  const clearTimer = React.useRef<number | null>(null);

  const scheduleClear = () => {
    if (clearTimer.current) window.clearTimeout(clearTimer.current);
    clearTimer.current = window.setTimeout(() => setStatus({ phase: "idle" }), 8000);
  };

  React.useEffect(
    () => () => {
      if (clearTimer.current) window.clearTimeout(clearTimer.current);
    },
    []
  );

  const startTriage = React.useCallback(async () => {
    if (running.current || !user) return;
    running.current = true;
    if (clearTimer.current) window.clearTimeout(clearTimer.current);
    setStatus({ phase: "running", index: 0, total: 0, subject: "Connecting to mailbox…" });
    try {
      const token = await getGraphAccessToken();
      if (!token) throw new Error("Mail.Read sign-in is required to run triage.");
      await runTriage(user.specialistId, token, (event) => {
        if (event.type === "run_started") {
          setStatus({ phase: "running", index: 0, total: event.total, subject: "Starting…" });
        } else if (event.type === "email_started") {
          setStatus({
            phase: "running",
            index: event.index,
            total: event.total,
            subject: event.subject || "(no subject)",
          });
        } else if (event.type === "run_finished") {
          setStatus({
            phase: "done",
            succeeded: event.succeeded,
            failed: event.failed,
            skipped: event.skipped,
          });
        } else if (event.type === "error") {
          setStatus({ phase: "error", message: event.message });
        }
      });
      setRunCount((n) => n + 1);
    } catch (err) {
      setStatus({ phase: "error", message: err instanceof Error ? err.message : String(err) });
    } finally {
      running.current = false;
      scheduleClear();
    }
  }, [user, getGraphAccessToken]);

  const value = React.useMemo(
    () => ({ status, isRunning: status.phase === "running", runCount, startTriage }),
    [status, runCount, startTriage]
  );

  return <TriageRunContext.Provider value={value}>{children}</TriageRunContext.Provider>;
}

export function useTriageRun(): TriageRunContextValue {
  const ctx = React.useContext(TriageRunContext);
  if (!ctx) throw new Error("useTriageRun must be used within TriageRunProvider");
  return ctx;
}
