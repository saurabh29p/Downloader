/** Pull download links out of pasted text or a .txt file: one or many, any separators. */
export function parseLinks(text: string): string[] {
  const seen = new Set<string>();
  const links: string[] = [];
  for (const raw of text.split(/[\s,]+/)) {
    const token = raw
      .trim()
      .replace(/^[<("'[]+/, "")
      .replace(/[>)"'\].,;]+$/, "");
    if (!token || token.startsWith("#")) continue;
    const looksLikeLink =
      /^(https?:\/\/|magnet:)/i.test(token) || /^[\w-]+(\.[\w-]+)+(:\d+)?(\/\S*)?$/.test(token);
    if (!looksLikeLink || seen.has(token)) continue;
    seen.add(token);
    links.push(token);
  }
  return links;
}

/** Host name to show for a URL, or the URL itself if it cannot be parsed. */
export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
