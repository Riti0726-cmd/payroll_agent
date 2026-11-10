import * as React from "react";
import { lookupEmail } from "../../api/workbench";
import { useSpecialist } from "../../auth/useSpecialist";
import type { CurrentItem } from "../../office/mailbox";
import type { EmailRecord } from "../../types/domain";

export interface EmailRecordState {
  record: EmailRecord | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
  update: (patch: Partial<EmailRecord>) => void;
}

/** Load the agent's triage record for the selected email. */
export function useEmailRecord(item: CurrentItem | null): EmailRecordState {
  const { user, getAccessToken } = useSpecialist();
  const [record, setRecord] = React.useState<EmailRecord | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [nonce, setNonce] = React.useState(0);
  const specialistId = user?.specialistId;

  React.useEffect(() => {
    if (!item || !specialistId) {
      setRecord(null);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const token = await getAccessToken();
        const found = await lookupEmail(
          specialistId,
          { restId: item.restId, internetMessageId: item.internetMessageId },
          token
        );
        if (!cancelled) setRecord(found);
      } catch (err) {
        if (!cancelled) {
          setRecord(null);
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // getAccessToken identity changes with auth state; specialistId covers that.
  }, [item?.restId, item?.internetMessageId, specialistId, nonce]);

  const reload = React.useCallback(() => setNonce((n) => n + 1), []);
  const update = React.useCallback(
    (patch: Partial<EmailRecord>) => setRecord((prev) => (prev ? { ...prev, ...patch } : prev)),
    []
  );

  return { record, loading, error, reload, update };
}
