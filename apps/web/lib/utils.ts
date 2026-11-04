import { clsx, type ClassValue } from "clsx";

/**
 * Join class names. Note: this does not resolve Tailwind conflicts (no
 * tailwind-merge, to keep the bundle small) — components must not receive
 * classes that fight their own (e.g. two different paddings).
 */
export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}
