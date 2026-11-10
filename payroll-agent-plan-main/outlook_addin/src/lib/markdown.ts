// Draft markdown → reply HTML. Supports the subset the drafting agent emits
// (paragraphs, "-"/"*" bullets, **bold**), same as web/src/components/MarkdownBody.tsx.

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function inline(text: string): string {
  return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

/** Drop the "**Triaged Category:** / **Employee ID:**" header the drafter prepends. */
export function stripDraftMeta(markdown: string): string {
  const lines = markdown.replace(/\r\n/g, "\n").trim().split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i].trim();
    if (!line || /^\*\*(Triaged Category|Employee ID):\*\*/i.test(line)) {
      i += 1;
      continue;
    }
    break;
  }
  return lines.slice(i).join("\n").trim();
}

export function markdownToHtml(markdown: string): string {
  const lines = stripDraftMeta(markdown).split("\n");
  const out: string[] = [];
  let para: string[] = [];
  let list: string[] = [];

  const flushPara = () => {
    if (para.length) out.push(`<p>${para.map(inline).join("<br>")}</p>`);
    para = [];
  };
  const flushList = () => {
    if (list.length)
      out.push(`<ul>${list.map((item) => `<li>${inline(item)}</li>`).join("")}</ul>`);
    list = [];
  };

  for (const line of lines) {
    const bullet = /^\s*[-*]\s+(.+)$/.exec(line);
    if (bullet) {
      flushPara();
      list.push(bullet[1].trim());
    } else if (!line.trim()) {
      flushList();
      flushPara();
    } else {
      flushList();
      para.push(line.trim());
    }
  }
  flushList();
  flushPara();
  return out.join("");
}
