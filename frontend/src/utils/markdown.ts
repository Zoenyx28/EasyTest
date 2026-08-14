/**
 * Simple Markdown to HTML converter.
 * Supports: headings, bold, italic, code (inline/block), links, lists, line breaks,
 * and auto-linking of http(s) URLs / IPv4:port addresses (kept out of code spans).
 */
export function renderMarkdown(text: string): string {
  if (!text) return '';

  let html = text;

  // Escape HTML special chars first
  html = html
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Protect code blocks / inline code so markdown & auto-link rules never touch them
  const codeBlocks: string[] = [];
  const codeSpans: string[] = [];
  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_m, _lang, code) => {
    codeBlocks.push(code.trim());
    return `\u0000CODEBLOCK${codeBlocks.length - 1}\u0000`;
  });
  html = html.replace(/`([^`]+)`/g, (_m, code) => {
    codeSpans.push(code);
    return `\u0000CODESPAN${codeSpans.length - 1}\u0000`;
  });

  // Headings (must be at start of line)
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // Bold and italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Images ![alt](url) — before the link rule so it isn't treated as a link
  const imgs: string[] = [];
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_m, alt, url) => {
    imgs.push(`<img src="${url}" alt="${alt}" style="max-width:100%;border-radius:8px;margin:6px 0;" />`);
    return `\u0000IMG${imgs.length - 1}\u0000`;
  });

  // Tables: consecutive pipe rows → <table> (placeholder to dodge later rules)
  const tables: string[] = [];
  html = html.replace(/((?:\|[^\n]+\|\n?)+)/g, (m) => {
    const rows = m.trim().split('\n').filter((r) => r.trim().startsWith('|'));
    if (rows.length < 2) return m;
    const cells = (r: string) => r.split('|').filter((c) => c.trim() !== '').map((c) => c.trim());
    const header = cells(rows[0]);
    const body = rows.slice(2).map(cells);
    const th = header.map((h) => `<th style="border:1px solid var(--border);padding:4px 8px;background:var(--bg-soft);">${h}</th>`).join('');
    const trs = body.map((r) => `<tr>${r.map((c) => `<td style="border:1px solid var(--border);padding:4px 8px;">${c}</td>`).join('')}</tr>`).join('');
    tables.push(`<table style="border-collapse:collapse;width:100%;font-size:12px;margin:6px 0;">` +
      `<thead><tr>${th}</tr></thead><tbody>${trs}</tbody></table>`);
    return `\u0000TABLE${tables.length - 1}\u0000`;
  });

  // Links [text](url)
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  // Auto-link http(s) URLs and IPv4[:port][/path] — protect existing anchors first
  const anchors: string[] = [];
  html = html.replace(/<a [^>]*>[\s\S]*?<\/a>/g, (m) => {
    anchors.push(m);
    return `\u0000ANCHOR${anchors.length - 1}\u0000`;
  });
  html = html.replace(
    /(^|[^a-zA-Z0-9_.:-])((?:https?:\/\/[^\s<>"'`）】,，;；。\u4e00-\u9fff]*|(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?(?:\/[^\s<>"'`）】,，;；。\u4e00-\u9fff]*)?))/g,
    (_m, pre, url) => {
      // Strip trailing punctuation so it stays outside the link
      const trimSet = new Set(['.', ',', '!', '?', ')', ']', '}']);
      let clean = url;
      while (clean.length && trimSet.has(clean[clean.length - 1])) clean = clean.slice(0, -1);
      if (!clean) return _m;
      const tail = url.slice(clean.length); // trailing punctuation, keep it outside the link
      const href = /^https?:\/\//i.test(clean) ? clean : `http://${clean}`;
      return `${pre}<a href="${href}" target="_blank" rel="noopener">${clean}</a>${tail}`;
    },
  );
  html = html.replace(/\u0000ANCHOR(\d+)\u0000/g, (_m, i) => anchors[+i]);

  // Unordered lists
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');

  // Line breaks (double newline = paragraph)
  html = html.replace(/\n\n/g, '</p><p>');
  html = html.replace(/\n/g, '<br>');

  // Restore images / tables
  html = html.replace(/\u0000IMG(\d+)\u0000/g, (_m, i) => imgs[+i]);
  html = html.replace(/\u0000TABLE(\d+)\u0000/g, (_m, i) => tables[+i]);

  // Restore code blocks / inline code
  html = html.replace(/\u0000CODEBLOCK(\d+)\u0000/g, (_m, i) => `<pre><code>${codeBlocks[+i]}</code></pre>`);
  html = html.replace(/\u0000CODESPAN(\d+)\u0000/g, (_m, i) => `<code>${codeSpans[+i]}</code>`);

  // Wrap in paragraph if not already wrapped
  if (!html.startsWith('<')) {
    html = '<p>' + html + '</p>';
  }

  return html;
}
