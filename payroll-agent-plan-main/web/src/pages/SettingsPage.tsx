import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchSettings,
  saveSettings,
  SettingsError,
  type SettingsInterval,
  type SettingsMode,
  type SettingsRun,
} from "../api/settings";
import { useSpecialist } from "../auth/useSpecialist";
import { Toast } from "../components/Toast";
import { animateEnter } from "../lib/animateEnter";
import { useTriageRun } from "../triage/TriageRunContext";
import styles from "./SettingsPage.module.css";

function formatStartedAt(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value || "—";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function SettingsPage() {
  const rootRef = useRef<HTMLDivElement>(null);
  const { displayName, getAccessToken, signOut, specialistId } = useSpecialist();
  const { isRunning: isRunningTriage, startTriage } = useTriageRun();
  const [lookbackDays, setLookbackDays] = useState(7);
  const [mode, setMode] = useState<SettingsMode>("manual");
  const [interval, setInterval] = useState<SettingsInterval>(2);
  const [runs, setRuns] = useState<SettingsRun[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    animateEnter(rootRef.current);
  }, []);

  useEffect(() => {
    if (!toast) {
      return undefined;
    }

    const timeout = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const loadSettings = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const token = await getAccessToken();
      const data = await fetchSettings(specialistId, token);
      setLookbackDays(data.lookbackDays);
      setMode(data.mode);
      setInterval(data.intervalHours);
      setRuns(data.runs ?? []);
    } catch (caught) {
      const message =
        caught instanceof SettingsError || caught instanceof Error
          ? caught.message
          : "Unable to load settings.";
      setLoadError(message);
    } finally {
      setIsLoading(false);
    }
  }, [getAccessToken, specialistId]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  async function handleSave() {
    setIsSaving(true);
    setToast(null);
    try {
      const token = await getAccessToken();
      const data = await saveSettings(
        specialistId,
        {
          lookbackDays,
          mode,
          intervalHours: interval,
        },
        token,
      );
      setLookbackDays(data.lookbackDays);
      setMode(data.mode);
      setInterval(data.intervalHours);
      setRuns(data.runs ?? []);
      setToast("Configuration saved.");
    } catch (caught) {
      const message =
        caught instanceof SettingsError || caught instanceof Error
          ? caught.message
          : "Unable to save settings.";
      setToast(message);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleRunTriage() {
    await startTriage();
    await loadSettings();
  }

  async function handleSignOut() {
    setIsSigningOut(true);
    setToast(null);
    try {
      await signOut();
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Unable to sign out.";
      setToast(message);
    } finally {
      setIsSigningOut(false);
    }
  }

  return (
    <div className={styles.page} ref={rootRef}>
      <section className={styles.header} data-enter>
        <div>
          <span className={styles.eyebrow}>Specialist controls</span>
          <h2>Settings</h2>
        </div>
        <button
          className="btn-primary"
          type="button"
          onClick={handleRunTriage}
          disabled={isRunningTriage}
        >
          {isRunningTriage ? "Running triage" : "Run triage"}
        </button>
      </section>

      <section className={styles.panel} aria-labelledby="triage-config-heading" data-enter>
        <div className={styles.panelHeader}>
          <div>
            <span className={styles.eyebrow}>Configuration</span>
            <h3 id="triage-config-heading">Triage schedule</h3>
          </div>
          <button type="button" onClick={handleSave} disabled={isSaving || isLoading}>
            {isSaving ? "Saving…" : "Save configuration"}
          </button>
        </div>

        {loadError ? (
          <div className={styles.formGrid}>
            <p>{loadError}</p>
            <button type="button" onClick={() => void loadSettings()}>
              Retry
            </button>
          </div>
        ) : (
          <div className={styles.formGrid}>
            <label>
              <span>Lookback days</span>
              <input
                min={1}
                type="number"
                value={lookbackDays}
                disabled={isLoading}
                onChange={(event) => setLookbackDays(Number(event.target.value))}
              />
            </label>
            <label>
              <span>Mode</span>
              <select
                value={mode}
                disabled={isLoading}
                onChange={(event) => setMode(event.target.value as SettingsMode)}
              >
                <option value="manual">Manual</option>
                <option value="recurring">Recurring</option>
              </select>
            </label>
            <label>
              <span>Interval</span>
              <select
                value={interval}
                disabled={isLoading}
                onChange={(event) => setInterval(Number(event.target.value) as SettingsInterval)}
              >
                <option value={2}>Every 2 hours</option>
                <option value={4}>Every 4 hours</option>
                <option value={24}>Every 24 hours</option>
              </select>
            </label>
          </div>
        )}
      </section>

      <section className={styles.panel} aria-labelledby="run-history-heading" data-enter>
        <div className={styles.panelHeader}>
          <div>
            <span className={styles.eyebrow}>Activity</span>
            <h3 id="run-history-heading">Run history</h3>
          </div>
        </div>

        <table className={styles.history}>
          <thead>
            <tr>
              <th>Started</th>
              <th>Status</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {runs.length === 0 ? (
              <tr>
                <td colSpan={3}>{isLoading ? "Loading…" : "No run history yet"}</td>
              </tr>
            ) : (
              runs.map((run) => (
                <tr key={run.runId || `${run.startedAt}-${run.status}`}>
                  <td>{formatStartedAt(run.startedAt)}</td>
                  <td>{run.status}</td>
                  <td>{run.result || "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>

      <section className={styles.panel} aria-labelledby="account-heading" data-enter>
        <div className={styles.panelHeader}>
          <div>
            <span className={styles.eyebrow}>Account</span>
            <h3 id="account-heading">Signed in</h3>
          </div>
          <button type="button" onClick={() => void handleSignOut()} disabled={isSigningOut}>
            {isSigningOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
        <p className={styles.accountName}>{displayName}</p>
      </section>

      <Toast message={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}
