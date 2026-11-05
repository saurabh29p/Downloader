/** Tiny toast store (replaces a 24 KB library). Read with useToasts(). */
import { useSyncExternalStore } from "react";

export type Toast = {
  id: number;
  kind: "success" | "error" | "info";
  message: string;
  description?: string;
  action?: { label: string; run: () => void };
};

type Options = { description?: string; action?: Toast["action"] };

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

function push(kind: Toast["kind"], message: string, options?: Options) {
  const item: Toast = { id: nextId++, kind, message, ...options };
  toasts = [...toasts.slice(-3), item];
  emit();
  setTimeout(() => dismissToast(item.id), DURATION);
  return item.id;
}

export const toast = {
  success: (message: string, options?: Options) => push("success", message, options),
  error: (message: string, options?: Options) => push("error", message, options),
  info: (message: string, options?: Options) => push("info", message, options),
};

/**
 * Show `message` with an Undo button and run `commit` when the toast ends.
 * Undo runs `undo` instead. The caller hides the thing at once (optimistic).
 */
export function withUndo(message: string, undoLabel: string, commit: () => void, undo: () => void) {
  const timer = setTimeout(commit, DURATION);
  push("info", message, {
    action: {
      label: undoLabel,
      run: () => {
        clearTimeout(timer);
        undo();
      },
    },
  });
}

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
