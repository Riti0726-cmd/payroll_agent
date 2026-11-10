import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { FoundryError } from "../api/foundry";
import { runTriageStream, TriageStreamError } from "../api/triage";
import { useSpecialist } from "../auth/useSpecialist";

export type TriageLiveStatus =
  | { phase: "idle" }
  | {
      phase: "running";
      index: number;
      total: number;
      subject: string;
      category?: string;
    }
  | {
      phase: "done";
      succeeded: number;
      failed: number;
      skipped: number;
    }
  | { phase: "error"; message: string };

type TriageRunContextValue = {
  status: TriageLiveStatus;
  isRunning: boolean;
  toast: string | null;
  setToast: (message: string | null) => void;
  startTriage: () => Promise<void>;
};

const TriageRunContext = createContext<TriageRunContextValue | null>(null);

function formatTriageError(error: unknown) {
  if (error instanceof TriageStreamError || error instanceof FoundryError) {
    return `Triage failed: ${error.message}`;
  }
  if (error instanceof Error) {
    return `Triage failed: ${error.message}`;
  }
  return "Triage failed.";
}

export function TriageRunProvider({ children }: { children: ReactNode }) {
  const { getGraphAccessToken, specialistId } = useSpecialist();
  const [status, setStatus] = useState<TriageLiveStatus>({ phase: "idle" });
  const [isRunning, setIsRunning] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const runningRef = useRef(false);
  const clearTimerRef = useRef<number | null>(null);

  const startTriage = useCallback(async () => {
    if (runningRef.current) {
      return;
    }
    runningRef.current = true;
    setIsRunning(true);
    if (clearTimerRef.current != null) {
      window.clearTimeout(clearTimerRef.current);
      clearTimerRef.current = null;
    }
    setStatus({ phase: "running", index: 0, total: 0, subject: "Starting…" });
    setToast("Starting triage… acquiring Mail.Read token");

    try {
      let token: string | undefined;
      try {
        token = await Promise.race([
          getGraphAccessToken(),
          new Promise<undefined>((_, reject) =>
            window.setTimeout(
              () => reject(new Error("Mail.Read sign-in timed out (popup blocked?)")),
              45_000,
            ),
          ),
        ]);
      } catch (tokenErr) {
        const msg =
          tokenErr instanceof Error ? tokenErr.message : "Could not acquire Mail.Read token";
        setStatus({ phase: "error", message: msg });
        setToast(`Triage blocked: ${msg}. Sign in and allow the popup for Mail.Read.`);
        return;
      }

      if (!token) {
        const msg = "no Mail.Read token";
        setStatus({ phase: "error", message: msg });
        setToast(
          "Triage blocked: no Mail.Read token. Sign in (Engage account), allow Mail.Read consent, then try again.",
        );
        return;
      }

      setToast("Running triage against your mailbox…");
      let sawTerminal = false;

      await runTriageStream(specialistId, token, (event) => {
        if (event.type === "run_started") {
          setStatus({
            phase: "running",
            index: 0,
            total: event.total,
            subject: event.total ? "Listing mailbox…" : "No messages in window",
          });
        } else if (event.type === "email_started") {
          setStatus({
            phase: "running",
            index: event.index,
            total: event.total,
            subject: event.subject || "(no subject)",
          });
        } else if (event.type === "email_finished") {
          setStatus({
            phase: "running",
            index: event.index,
            total: event.total,
            subject: event.subject || "(no subject)",
            category: event.category ?? undefined,
          });
        } else if (event.type === "run_finished") {
          sawTerminal = true;
          setStatus({
            phase: "done",
            succeeded: event.succeeded,
            failed: event.failed,
            skipped: event.skipped,
          });
          setToast(
            `Triage run completed: ${event.succeeded} ok, ${event.failed} failed, ${event.skipped} skipped`,
          );
        } else if (event.type === "error") {
          sawTerminal = true;
          setStatus({ phase: "error", message: event.message });
          setToast(`Triage failed: ${event.message}`);
        }
      });

      if (!sawTerminal) {
        setStatus({ phase: "done", succeeded: 0, failed: 0, skipped: 0 });
        setToast("Triage run completed.");
      }
    } catch (caught) {
      console.error("Run triage failed", caught);
      const message = formatTriageError(caught);
      setStatus({ phase: "error", message });
      setToast(message);
    } finally {
      runningRef.current = false;
      setIsRunning(false);
      clearTimerRef.current = window.setTimeout(() => {
        setStatus({ phase: "idle" });
        clearTimerRef.current = null;
      }, 8000);
    }
  }, [getGraphAccessToken, specialistId]);

  const value = useMemo(
    () => ({
      status,
      isRunning,
      toast,
      setToast,
      startTriage,
    }),
    [status, isRunning, toast, startTriage],
  );

  return <TriageRunContext.Provider value={value}>{children}</TriageRunContext.Provider>;
}

export function useTriageRun() {
  const ctx = useContext(TriageRunContext);
  if (!ctx) {
    throw new Error("useTriageRun must be used within TriageRunProvider");
  }
  return ctx;
}
