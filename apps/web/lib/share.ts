/** The first http(s) link in shared text (Android apps often share "Title https://…"). */
export function firstLink(parts: (string | undefined)[]): string | null {
  for (const part of parts) {
    const match = part?.match(/https?:\/\/[^\s<>"']+/i);
    if (match) return match[0].replace(/[),.;!?\]]+$/, "");
  }
  return null;
}
