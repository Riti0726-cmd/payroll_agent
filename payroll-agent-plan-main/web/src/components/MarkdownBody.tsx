import type { ReactNode } from "react";
import styles from "./MarkdownBody.module.css";

type Block =
  | { type: "p"; text: string }
  | { type: "ul"; items: string[] }
  | { type: "meta"; category: string; employeeId: string };

function parseInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const re = /\*\*(.+?)\*\*/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push(text.slice(last, match.index));
    }
    nodes.push(
      <strong key={`b-${key++}`} className={styles.strong}>
        {match[1]}
      </strong>,
    );
    last = match.index + match[0].length;
  }
  if (last < text.length) {
    nodes.push(text.slice(last));
  }
  return nodes.length > 0 ? nodes : [text];
}

function extractMeta(raw: string): { meta: Block | null; rest: string } {
  const lines = raw.replace(/\r\n/g, "\n").trim().split("\n");
  let category = "";
  let employeeId = "";
  let i = 0;
  while (i < lines.length) {
    const line = lines[i]?.trim() ?? "";
    if (!line) {
      i += 1;
      continue;
    }
    const cat = /^\*\*Triaged Category:\*\*\s*(.+)$/i.exec(line);
    if (cat) {
      category = cat[1].trim();
      i += 1;
      continue;
    }
    const emp = /^\*\*Employee ID:\*\*\s*(.+)$/i.exec(line);
    if (emp) {
      employeeId = emp[1].trim();
      i += 1;
      continue;
    }
    break;
  }
  if (!category && !employeeId) {
    return { meta: null, rest: raw };
  }
  return {
    meta: { type: "meta", category: category || "—", employeeId: employeeId || "—" },
    rest: lines.slice(i).join("\n").trim(),
  };
}

function parseBlocks(raw: string): Block[] {
  const { meta, rest } = extractMeta(raw);
  const blocks: Block[] = [];
  if (meta) {
    blocks.push(meta);
  }
  if (!rest) {
    return blocks;
  }

  const lines = rest.replace(/\r\n/g, "\n").split("\n");
  let para: string[] = [];
  let list: string[] = [];

  const flushPara = () => {
    if (para.length === 0) return;
    blocks.push({ type: "p", text: para.join(" ").trim() });
    para = [];
  };
  const flushList = () => {
    if (list.length === 0) return;
    blocks.push({ type: "ul", items: [...list] });
    list = [];
  };

  for (const line of lines) {
    const bullet = /^\s*[-*]\s+(.+)$/.exec(line);
    if (bullet) {
      flushPara();
      list.push(bullet[1].trim());
      continue;
    }
    if (!line.trim()) {
      flushList();
      flushPara();
      continue;
    }
    flushList();
    para.push(line.trim());
  }
  flushList();
  flushPara();
  return blocks;
}

export function MarkdownBody({ source, emptyLabel }: { source: string; emptyLabel?: string }) {
  const trimmed = source.trim();
  if (!trimmed) {
    return <p className={styles.empty}>{emptyLabel ?? "No content."}</p>;
  }

  const blocks = parseBlocks(trimmed);

  return (
    <div className={styles.root}>
      {blocks.map((block, index) => {
        if (block.type === "meta") {
          return (
            <div className={styles.meta} key={`meta-${index}`}>
              <div>
                <span className={styles.metaLabel}>Category</span>
                <strong className={styles.metaValue}>{block.category}</strong>
              </div>
              <div>
                <span className={styles.metaLabel}>Employee</span>
                <strong className={styles.metaValue}>{block.employeeId}</strong>
              </div>
            </div>
          );
        }
        if (block.type === "ul") {
          return (
            <ul className={styles.list} key={`ul-${index}`}>
              {block.items.map((item, itemIndex) => (
                <li key={`li-${index}-${itemIndex}`}>{parseInline(item)}</li>
              ))}
            </ul>
          );
        }
        return (
          <p className={styles.paragraph} key={`p-${index}`}>
            {parseInline(block.text)}
          </p>
        );
      })}
    </div>
  );
}
