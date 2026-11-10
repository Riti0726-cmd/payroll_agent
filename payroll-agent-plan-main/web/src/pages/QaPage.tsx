import { type FormEvent, useEffect, useRef, useState } from "react";
import {
  formatQaSource,
  invokeQaChat,
  QaError,
  sourceHasTracePanes,
  type QaSource,
} from "../api/qa";
import { useSpecialist } from "../auth/useSpecialist";
import { animateEnter } from "../lib/animateEnter";
import type { ChatMessage } from "../types/domain";
import styles from "./QaPage.module.css";

type InlineError = {
  detail: string;
  input: string;
};

function createMessageId() {
  return `qa-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function getErrorDetail(error: unknown) {
  if (error instanceof QaError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Unable to complete the Q&A request.";
}

function toChatTurns(messages: ChatMessage[]) {
  return messages.map((message) => ({
    role: message.role,
    content: message.content,
  }));
}

function ToolTraceChips({ sources }: { sources: QaSource[] }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});

  if (!sources.length) {
    return null;
  }

  return (
    <aside className={styles.sources} aria-label="Used tools">
      <span>Used tools</span>
      <ul className={styles.toolList}>
        {sources.map((source, index) => {
          const key = `${source.label}-${index}`;
          const expandable = sourceHasTracePanes(source);
          const isOpen = Boolean(open[key]);
          const summary = formatQaSource(source);

          return (
            <li key={key} className={styles.toolItem}>
              {expandable ? (
                <button
                  type="button"
                  className={styles.toolChip}
                  aria-expanded={isOpen}
                  onClick={() =>
                    setOpen((current) => ({
                      ...current,
                      [key]: !current[key],
                    }))
                  }
                >
                  <span className={styles.toolChipLabel}>{source.label}</span>
                  {source.detail ? (
                    <span className={styles.toolChipDetail}>{source.detail}</span>
                  ) : null}
                </button>
              ) : (
                <div className={styles.toolChipStatic}>{summary}</div>
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

export function QaPage() {
  const rootRef = useRef<HTMLDivElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const { getAccessToken } = useSpecialist();
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<InlineError | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  useEffect(() => {
    animateEnter(rootRef.current);
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({
      top: logRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [error, isLoading, messages]);

  async function submitToQa(input: string, appendUserMessage: boolean) {
    setError(null);
    setIsLoading(true);

    const history: ChatMessage[] = appendUserMessage
      ? [
          ...messages,
          {
            id: createMessageId(),
            role: "user",
            content: input,
          },
        ]
      : messages;

    if (appendUserMessage) {
      setMessages(history);
    }

    try {
      const token = await getAccessToken();
      const reply = await invokeQaChat(toChatTurns(history), token);
      setMessages((current) => [
        ...current,
        {
          id: createMessageId(),
          role: "assistant",
          content: reply.answer,
          toolSources: reply.sources,
          sources: reply.sources.map(formatQaSource),
        },
      ]);
    } catch (caught) {
      setError({
        input,
        detail: getErrorDetail(caught),
      });
    } finally {
      setIsLoading(false);
    }
  }

  async function onSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmed = draft.trim();
    if (!trimmed || isLoading) {
      return;
    }

    setDraft("");
    await submitToQa(trimmed, true);
  }

  async function onRetry() {
    if (!error || isLoading) {
      return;
    }

    await submitToQa(error.input, false);
  }

  const canSend = draft.trim().length > 0 && !isLoading;

  return (
    <div className={styles.page} ref={rootRef}>
      <section className={styles.header} data-enter>
        <div>
          <span className={styles.eyebrow}>Q&A console</span>
          <h2>Ask as a payroll specialist</h2>
        </div>
        <p>
          Investigate payroll and employee data with Cortex MCP. Answers are for you (the
          specialist), not employee-facing replies. Full chat history is sent on each turn.
        </p>
      </section>

      <section className={styles.chatPanel} aria-label="Payroll Q&A chat" data-enter>
        <div className={styles.log} ref={logRef}>
          {messages.length === 0 ? (
            <div className={styles.emptyState}>
              <span className={styles.emptyKicker}>Standing by</span>
              <h3>Investigate pay, deductions, and employee payroll context.</h3>
              <p>
                Ask about a specific employee, period, or variance. Replies come from POST /qa for
                specialist use — not the email triage or employee-draft pipeline.
              </p>
            </div>
          ) : (
            messages.map((message) => (
              <article
                className={
                  message.role === "user"
                    ? `${styles.message} ${styles.userMessage}`
                    : `${styles.message} ${styles.assistantMessage}`
                }
                key={message.id}
              >
                <span className={styles.messageRole}>
                  {message.role === "user" ? "Specialist" : "Q&A agent"}
                </span>
                <p className={styles.messageBody}>
                  {message.content.trim() ||
                    (message.role === "assistant"
                      ? "No answer was returned. Expand Used tools for Cortex details, or retry."
                      : "")}
                </p>
                {message.role === "assistant" && message.toolSources?.length ? (
                  <ToolTraceChips sources={message.toolSources} />
                ) : null}
              </article>
            ))
          )}

          {isLoading ? (
            <article className={`${styles.message} ${styles.assistantMessage} ${styles.loading}`}>
              <span className={styles.messageRole}>Q&A agent</span>
              <p>Requesting answer...</p>
            </article>
          ) : null}

          {error ? (
            <div className={styles.errorBox} role="alert">
              <div>
                <span className={styles.errorLabel}>Q&A request failed</span>
                <p>{error.detail}</p>
              </div>
              <button type="button" onClick={onRetry} disabled={isLoading}>
                Retry
              </button>
            </div>
          ) : null}
        </div>

        <form className={styles.composer} onSubmit={onSend}>
          <label htmlFor="qa-input">Question</label>
          <div className={styles.composerRow}>
            <textarea
              id="qa-input"
              placeholder="Why was EMP-123's August net pay lower?"
              rows={3}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
            />
            <button className="btn-primary" type="submit" disabled={!canSend}>
              {isLoading ? "Sending" : "Send"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
