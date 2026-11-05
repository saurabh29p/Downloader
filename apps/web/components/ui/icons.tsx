import type { ReactNode } from "react";

// Tiny inline icons for the app shell: a lucide icon module costs ~0.5 KB here.
function icon(path: ReactNode) {
  return function Icon({ className }: { className?: string }) {
    return (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className={className}
      >
        {path}
      </svg>
    );
  };
}

export const ChevronDown = icon(<path d="m6 9 6 6 6-6" />);
export const Contrast = icon(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor" />
  </>,
);
export const Globe = icon(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3" />
  </>,
);
export const Close = icon(<path d="M18 6 6 18M6 6l12 12" />);
