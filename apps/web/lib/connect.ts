/** Errors that signing in on the user's own account usually fixes. */
const CONNECT_CODES = ["login_required", "bot_check", "age_restricted", "forbidden"];

/** Host (or parent domain) → site name. */
const SITES: Record<string, string> = {
  "youtube.com": "YouTube",
  "youtu.be": "YouTube",
  "x.com": "X",
  "twitter.com": "X",
  "reddit.com": "Reddit",
  "vimeo.com": "Vimeo",
  "instagram.com": "Instagram",
  "facebook.com": "Facebook",
  "fb.watch": "Facebook",
  "patreon.com": "Patreon",
};

/** The site to connect (id for links, label to show) when that fixes this error, else null. */
export function connectFor(
  code: string | null | undefined,
  url: string,
): { id: string; label: string } | null {
  if (!code || !CONNECT_CODES.includes(code)) return null;
  let host: string;
  try {
    host = new URL(url).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return null;
  }
  const domain = Object.keys(SITES).find((d) => host === d || host.endsWith(`.${d}`));
  const label = domain ? SITES[domain]! : host;
  return label ? { id: label.toLowerCase(), label } : null;
}
