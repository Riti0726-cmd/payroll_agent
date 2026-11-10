export type SettingsMode = "manual" | "recurring";
export type SettingsInterval = 2 | 4 | 24;

export interface SettingsRun {
  runId: string;
  startedAt: string;
  status: string;
  result: string;
}

export interface SettingsPayload {
  lookbackDays: number;
  mode: SettingsMode;
  intervalHours: SettingsInterval;
  runs: SettingsRun[];
}

export type SettingsUpdate = Omit<SettingsPayload, "runs">;

export class SettingsError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(describeSettingsFailure(status, body));
    this.status = status;
    this.body = body;
  }
}

function describeSettingsFailure(status: number, body: string): string {
  const trimmed = body.trim();
  if (trimmed) {
    try {
      const parsed = JSON.parse(trimmed) as { detail?: string };
      if (parsed.detail) {
        return parsed.detail;
      }
    } catch {
      /* plain text */
    }
    return `Settings returned ${status}: ${trimmed}`;
  }
  return `Settings returned ${status}.`;
}

function settingsUrl(specialistId: string): string {
  const base = import.meta.env.VITE_SETTINGS_URL as string | undefined;
  if (!base) {
    throw new Error("VITE_SETTINGS_URL is not set");
  }
  const url = new URL(base, window.location.origin);
  url.searchParams.set("specialist_id", specialistId);
  return url.toString();
}

export async function fetchSettings(
  specialistId: string,
  accessToken?: string,
): Promise<SettingsPayload> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  let resp: Response;
  try {
    resp = await fetch(settingsUrl(specialistId), { method: "GET", headers });
  } catch {
    throw new SettingsError(502, "Network error reaching the settings API");
  }

  const body = await resp.text();
  if (!resp.ok) {
    throw new SettingsError(resp.status, body);
  }

  try {
    return JSON.parse(body) as SettingsPayload;
  } catch {
    throw new SettingsError(502, `Invalid settings response: ${body.slice(0, 200)}`);
  }
}

export async function saveSettings(
  specialistId: string,
  payload: SettingsUpdate,
  accessToken?: string,
): Promise<SettingsPayload> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  let resp: Response;
  try {
    resp = await fetch(settingsUrl(specialistId), {
      method: "PUT",
      headers,
      body: JSON.stringify(payload),
    });
  } catch {
    throw new SettingsError(502, "Network error reaching the settings API");
  }

  const body = await resp.text();
  if (!resp.ok) {
    throw new SettingsError(resp.status, body);
  }

  try {
    return JSON.parse(body) as SettingsPayload;
  } catch {
    throw new SettingsError(502, `Invalid settings response: ${body.slice(0, 200)}`);
  }
}
