import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** A native radio or checkbox styled as a pill; keyboard and screen readers work as usual. */
export function ChoicePill({
  type = "radio",
  name,
  value,
  checked,
  disabled,
  onChange,
  children,
  hint,
}: {
  type?: "radio" | "checkbox";
  name: string;
  value: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
  children: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <label
      className={cn(
        "inline-flex min-h-11 cursor-pointer flex-col items-center justify-center rounded-md border px-3 py-1.5 text-sm",
        "has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-ring/50",
        checked ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:bg-accent",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      <input
        type={type}
        name={name}
        value={value}
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="sr-only"
      />
      <span className="font-medium">{children}</span>
      {hint && (
        <span className={cn("text-xs", checked ? "opacity-90" : "text-muted-foreground")}>
          {hint}
        </span>
      )}
    </label>
  );
}

export function CheckRow({
  checked,
  onChange,
  children,
  disabled,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: ReactNode;
  disabled?: boolean;
}) {
  return (
    <label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="size-5 shrink-0 accent-primary"
      />
      <span>{children}</span>
    </label>
  );
}
