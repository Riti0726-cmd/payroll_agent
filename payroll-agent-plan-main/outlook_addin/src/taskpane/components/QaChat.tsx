// Port of web/src/pages/QaPage.tsx for the task pane, plus "Include this email".
import * as React from "react";
import { askQa, type QaChatTurn, type QaProgressEvent, type QaSource } from "../../api/streams";
import { useSpecialist } from "../../auth/useSpecialist";
import { getBodyText, type CurrentItem } from "../../office/mailbox";
import styles from "./QaChat.module.css";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: QaSource[];
}

/** Keep the email context bounded; long threads add little and cost latency. */
const MAX_EMAIL_CHARS = 6000;

const SUGGESTIONS = [
  "Summarize this employee's last three pay periods",
  "Is this rate change consistent with their history?",
  "What deductions changed this period?",
];

function formatElapsed(elapsedMs: number): string {
  const seconds = Math.floor(elapsedMs / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${(seconds % 60).toString().padStart(2, "0")}s`;
}

function ThinkingIndicator({ statusLabel }: { statusLabel: string }) {
  const [elapsedMs, setElapsedMs] = React.useState(0);
  React.useEffect(() => {
    const started = Date.now();
    const tick = window.setInterval(() => setElapsedMs(Date.now() - started), 500);
    return () => window.clearInterval(tick);
  }, []);
  return (
    <article
      className={`${styles.message} ${styles.assistantMessage} ${styles.loading}`}
      aria-live="polite"
      aria-busy="true"
    >
      <span className={styles.messageRole}>Q&A agent</span>
      <div className={styles.thinkingRow}>
        <span className={styles.thinkingDots} aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <p className={styles.thinkingLabel}>{statusLabel}</p>
        <span className={styles.thinkingElapsed}>{formatElapsed(elapsedMs)}</span>
      </div>
      <p className={styles.thinkingHint}>Live Cortex progress — this often takes 15–45 seconds.</p>
    </article>
  );
}

function hasTracePanes(source: QaSource): boolean {
  return source.query != null || source.interpretation != null || source.response != null;
}

function ToolTraceChips({ sources }: { sources: QaSource[] }) {
  const [open, setOpen] = React.useState<Record<string, boolean>>({});
  if (!sources.length) return null;
  return (
    <aside className={styles.sources} aria-label="Used tools">
      <span>Used tools</span>
      <ul className={styles.toolList}>
        {sources.map((source, index) => {
          const key = `${source.label}-${index}`;
          const expandable = hasTracePanes(source);
          const isOpen = Boolean(open[key]);
          return (
            <li key={key} className={styles.toolItem}>
              {expandable ? (
                <button
                  type="button"
                  className={styles.toolChip}
                  aria-expanded={isOpen}
                  onClick={() => setOpen((current) => ({ ...current, [key]: !current[key] }))}
                >
                  <span className={styles.toolChipLabel}>{source.label}</span>
                  {source.detail ? <span className={styles.toolChipDetail}>{source.detail}</span> : null}
                </button>
              ) : (
                <div className={styles.toolChipStatic}>
                  {source.detail ? `${source.label}: ${source.detail}` : source.label}
                </div>
              )}
              {expandable && isOpen ? (
                <div className={styles.toolPanes}>
                  <section>
                    <h4>MCP query</h4>
                    <pre>{source.query ?? "Not returned by Cortex"}</pre>
                  </section>
                  <section>
                    <h4>Analyst interpretation</h4>
                    <pre>{source.interpretation ?? "Not returned by Cortex"}</pre>
                  </section>
                  <section>
                    <h4>Response</h4>
                    <pre>{source.response ?? "Not returned by Cortex"}</pre>
                  </section>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </aside>
  );
}

let nextId = 0;
const createId = () => `qa-${Date.now()}-${nextId++}`;

export function QaChat({ item }: { item: CurrentItem | null }) {
  const { getAccessToken } = useSpecialist();
  const [messages, setMessages] = React.useState<ChatMessage[]>([]);
  const [draft, setDraft] = React.useState("");
  const [includeEmail, setIncludeEmail] = React.useState(true);
  const [isLoading, setIsLoading] = React.useState(false);
  const [statusLabel, setStatusLabel] = React.useState("Contacting Q&A agent…");
  const [error, setError] = React.useState<{ detail: string; input: string } | null>(null);
  const logRef = React.useRef<HTMLDivElement>(null);
  const abort = React.useRef<AbortController | null>(null);

  React.useEffect(() => () => abort.current?.abort(), []);

  React.useEffect(() => {
    const log = logRef.current;
    if (log && typeof log.scrollTo === "function") {
      log.scrollTo({ top: log.scrollHeight, behavior: "smooth" });
    }
  }, [messages, isLoading, error, statusLabel]);

  const onProgress = (event: QaProgressEvent) => {
    if (event.type === "started") setStatusLabel("Planning…");
    else if (event.type === "tool_started") setStatusLabel(event.label);
    else if (event.type === "tool_finished") setStatusLabel("Planning next step…");
  };

  const submit = async (input: string, appendUserMessage: boolean) => {
    setError(null);
    setIsLoading(true);
    setStatusLabel("Contacting Q&A agent…");
    const history = appendUserMessage
      ? [...messages, { id: createId(), role: "user" as const, content: input }]
      : messages;
    if (appendUserMessage) setMessages(history);
    abort.current = new AbortController();

    try {
      const turns: QaChatTurn[] = history.map(({ role, content }) => ({ role, content }));
      const withEmail = includeEmail && Boolean(item);
      if (withEmail && item) {
        const body = (await getBodyText()).trim().slice(0, MAX_EMAIL_CHARS);
        turns[turns.length - 1] = {
          role: "user",
          content:
            `Context — the email I'm reading:\nFrom: ${item.from}\nSubject: ${item.subject}\n\n${body}` +
            `\n\nQuestion: ${input}`,
        };
      }
      const reply = await askQa(turns, await getAccessToken(), onProgress, abort.current.signal);
      setMessages((current) => [
        ...current,
        { id: createId(), role: "assistant", content: reply.answer, sources: reply.sources },
      ]);
    } catch (err) {
      if (!abort.current.signal.aborted) {
        setError({ input, detail: err instanceof Error ? err.message : String(err) });
      }
    } finally {
      setIsLoading(false);
    }
  };

  const onSend = (event?: React.FormEvent) => {
    event?.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed || isLoading) return;
    setDraft("");
    void submit(trimmed, true);
  };

  const canSend = draft.trim().length > 0 && !isLoading;

  return (
    <section className={styles.chatPanel} aria-label="Payroll Q&A chat" data-enter>
      <div className={styles.log} ref={logRef}>
        {messages.length === 0 && !isLoading ? (
          <div className={styles.emptyState}>
            <span className={styles.emptyKicker}>Standing by</span>
            <h3>Investigate pay, deductions and employee payroll context.</h3>
            <p>Answers are for you, the specialist, not employee-facing replies.</p>
            <div className={styles.suggestions}>
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className={styles.suggestion} onClick={() => setDraft(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) => (
            <article
              key={m.id}
              className={`${styles.message} ${m.role === "user" ? styles.userMessage : styles.assistantMessage}`}
            >
              <span className={styles.messageRole}>{m.role === "user" ? "Specialist" : "Q&A agent"}</span>
              <p className={styles.messageBody}>
                {m.content.trim() ||
                  (m.role === "assistant" ? "No answer was returned. Expand Used tools for details, or retry." : "")}
              </p>
              {m.role === "assistant" && m.sources?.length ? <ToolTraceChips sources={m.sources} /> : null}
            </article>
          ))
        )}

        {isLoading ? <ThinkingIndicator statusLabel={statusLabel} /> : null}

        {error ? (
          <div className={styles.errorBox} role="alert">
            <div>
              <span className={styles.errorLabel}>Q&A request failed</span>
              <p>{error.detail}</p>
            </div>
            <button type="button" disabled={isLoading} onClick={() => void submit(error.input, false)}>
              Retry
            </button>
          </div>
        ) : null}
      </div>

      <form className={styles.composer} onSubmit={onSend}>
        <div className={styles.composerHead}>
          <label htmlFor="qa-input">Question</label>
          <label className={styles.contextToggle}>
            <input
              type="checkbox"
              checked={includeEmail && Boolean(item)}
              disabled={!item}
              onChange={(event) => setIncludeEmail(event.target.checked)}
            />
            <span>Include this email</span>
          </label>
        </div>
        <textarea
          id="qa-input"
          placeholder="Why was EMP-1042's October net pay lower?"
          rows={3}
          value={draft}
          disabled={isLoading}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSend();
            }
          }}
        />
        <button className="btn-primary" type="submit" disabled={!canSend}>
          {isLoading ? "Working…" : "Send"}
        </button>
      </form>
    </section>
  );
}
