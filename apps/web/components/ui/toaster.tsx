"use client";

import { Close } from "@/components/ui/icons";
import { dismissToast, useToasts, type Toast } from "@/lib/toast";
import { cn } from "@/lib/utils";

function Item({ item, closeLabel }: { item: Toast; closeLabel: string }) {
  return (
    <li
      className={cn(
        "pointer-events-auto flex animate-in items-start gap-3 rounded-md border border-s-4 bg-popover p-3 text-popover-foreground shadow-lg fade-in-0 slide-in-from-bottom-2",
        item.kind === "success" && "border-s-success",
        item.kind === "error" && "border-s-destructive",
        item.kind === "info" && "border-s-signal",
      )}
      data-testid="toast"
    >
      <div className="min-w-0 flex-1 text-sm">
        <p className="font-medium break-words" dir="auto">
          {item.message}
        </p>
        {item.description && <p className="mt-0.5 text-muted-foreground">{item.description}</p>}
      </div>
      {item.action && (
        <button
          type="button"
          onClick={() => {
            item.action!.run();
            dismissToast(item.id);
          }}
          className="-my-1 h-8 shrink-0 rounded-md px-2 text-sm font-semibold text-primary hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          {item.action.label}
        </button>
      )}
      <button
        type="button"
        onClick={() => dismissToast(item.id)}
        className="-m-1 inline-flex size-8 shrink-0 items-center justify-center rounded-md opacity-70 hover:bg-accent hover:opacity-100 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        <Close className="size-4" />
        <span className="sr-only">{closeLabel}</span>
      </button>
    </li>
  );
}

/** Live regions: polite for success/info, assertive for errors. */
export function Toaster({ closeLabel }: { closeLabel: string }) {
  const items = useToasts();
  const errors = items.filter((t) => t.kind === "error");
  const others = items.filter((t) => t.kind !== "error");
  const listClass = "pointer-events-none flex flex-col gap-2 [&:empty]:hidden";
  return (
    <div
      data-toasts
      className="pointer-events-none fixed inset-x-4 bottom-[calc(var(--bottom-nav-height)+1rem)] z-50 flex flex-col gap-2 sm:start-auto sm:end-4 sm:bottom-4 sm:w-96"
    >
      <div role="status" aria-live="polite">
        <ol className={listClass}>
          {others.map((item) => (
            <Item key={item.id} item={item} closeLabel={closeLabel} />
          ))}
        </ol>
      </div>
      <div role="alert" aria-live="assertive">
        <ol className={listClass}>
          {errors.map((item) => (
            <Item key={item.id} item={item} closeLabel={closeLabel} />
          ))}
        </ol>
      </div>
    </div>
  );
}
