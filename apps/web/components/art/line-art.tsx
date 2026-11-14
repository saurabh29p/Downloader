import type { ReactNode } from "react";

/**
 * Darkroom line art: small single-stroke drawings in currentColor.
 * Server-rendered only (no client JS); always decorative (aria-hidden).
 */
const PATHS: Record<string, ReactNode> = {
  movies: (
    <>
      <rect x="6" y="12" width="36" height="26" rx="2" />
      <path d="M6 18h36M6 32h36M12 12v6M20 12v6M28 12v6M36 12v6M12 32v6M20 32v6M28 32v6M36 32v6" />
      <path d="m21 21 7 4-7 4z" />
    </>
  ),
  books: (
    <>
      <path d="M24 13c-5-3-11-3-17-1v24c6-2 12-2 17 1 5-3 11-3 17-1V12c-6-2-12-2-17 1z" />
      <path d="M24 13v24M11 18c3-1 6-1 9 0M11 23c3-1 6-1 9 0M28 18c3-1 6-1 9 0M28 23c3-1 6-1 9 0" />
    </>
  ),
  music: (
    <>
      <circle cx="24" cy="24" r="17" />
      <circle cx="24" cy="24" r="5" />
      <path d="M24 11a13 13 0 0 1 13 13M24 15a9 9 0 0 1 9 9" />
    </>
  ),
  video: (
    <>
      <rect x="6" y="15" width="26" height="20" rx="3" />
      <path d="m32 21 10-5v18l-10-5z" />
      <circle cx="13" cy="21" r="2" />
    </>
  ),
  declassified: (
    <>
      <path d="M6 14h13l3 4h20v20H6z" />
      <rect x="14" y="24" width="20" height="8" rx="1" transform="rotate(-6 24 28)" />
      <path d="M17 28h14" transform="rotate(-6 24 28)" />
    </>
  ),
  more: (
    <>
      <rect x="7" y="8" width="34" height="32" rx="2" />
      <path d="M7 19h34M7 30h34M20 13h8M20 24h8M20 35h8" />
    </>
  ),
  maps: (
    <>
      <path d="M6 12l11-4 14 4 11-4v28l-11 4-14-4-11 4z" />
      <path d="M17 8v28M31 12v28" />
      <path d="M21 22c2-3 6-3 7 0" strokeDasharray="2 2" />
    </>
  ),
  newspapers: (
    <>
      <path d="M10 10h28v28a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V18h4" />
      <path d="M10 10v28M15 16h18M15 22h8M15 28h8M15 34h8M27 22h6v12h-6z" />
    </>
  ),
  photos: (
    <>
      <path d="M6 16h8l3-4h14l3 4h8v22H6z" />
      <circle cx="24" cy="26" r="7" />
      <circle cx="36" cy="20" r="1" />
    </>
  ),
  manuscripts: (
    <>
      <path d="M12 8h22a4 4 0 0 1 0 8H14v22a4 4 0 0 1-8 0V14a6 6 0 0 1 6-6z" />
      <path d="M14 16h24v20a4 4 0 0 1-4 4H10M19 22h14M19 27h14M19 32h9" />
    </>
  ),
  lamp: (
    <>
      <path d="M18 6h12l6 14H12z" />
      <path d="M24 20v16M14 42h20M18 42l2-6h8l2 6" />
      <path d="M10 26l-3 3M38 26l3 3M24 24v0" strokeDasharray="1 3" />
    </>
  ),
  drawer: (
    <>
      <rect x="6" y="14" width="36" height="24" rx="2" />
      <rect x="17" y="20" width="14" height="6" rx="1" />
      <path d="M20 31h8M10 14l4-6h20l4 6" />
    </>
  ),
};

export type ArtName = keyof typeof PATHS;

export function LineArt({ name, className }: { name: ArtName; className?: string }) {
  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      {PATHS[name] ?? PATHS.drawer}
    </svg>
  );
}
