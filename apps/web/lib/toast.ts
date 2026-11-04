/** Tiny toast store (replaces a 24 KB library). Read with useToasts(). */
import { useSyncExternalStore } from "react";

export type Toast = {
  id: number;
  kind: "success" | "error" | "info";
  message: string;
  description?: string;
};

const DURATION = 5000;
let toasts: Toast[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

export function dismissToast(id: number) {
  toasts = toasts.filter((t) => t.id !== id);
  emit();
}

function push(kind: Toast["kind"], message: string, options?: { description?: string }) {
  const item: Toast = { id: nextId++, kind, message, description: options?.description };
  toasts = [...toasts.slice(-3), item];
  emit();
  setTimeout(() => dismissToast(item.id), DURATION);
  return item.id;
}

export const toast = {
  success: (message: string, options?: { description?: string }) =>
    push("success", message, options),
  error: (message: string, options?: { description?: string }) => push("error", message, options),
  info: (message: string, options?: { description?: string }) => push("info", message, options),
};

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

const EMPTY: Toast[] = [];

export function useToasts(): Toast[] {
  return useSyncExternalStore(
    subscribe,
    () => toasts,
    () => EMPTY,
  );
}
